import json
import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment, WebhookEvent
from app.schemas import WebhookPayload
from app.signature import SIGNATURE_HEADER, TIMESTAMP_HEADER, verify_signature
from app.state_machine import (
    InvalidTransitionError,
    OutOfOrderEventError,
    apply_transition,
)

logger = logging.getLogger(__name__)

MAX_BODY_SIZE = 5 * 1024 * 1024  # 5 MB limit


def create_app(webhook_secret: str = "test-secret") -> FastAPI:
    application = FastAPI(title="FulfillHub Webhook Receiver")
    application.state.webhook_secret = webhook_secret

    @application.post("/webhooks/yuno")
    async def receive_webhook(
        request: Request,
        db: Session = Depends(get_db),
    ) -> Response:
        # 1. Read raw body with size limit
        body = await request.body()
        if len(body) > MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"error": "Payload too large"})

        # 2. Verify signature → 401 if fails
        secret = request.app.state.webhook_secret
        sig = request.headers.get(SIGNATURE_HEADER, "")
        ts = request.headers.get(TIMESTAMP_HEADER, "")
        try:
            verify_signature(secret=secret, signature=sig, timestamp_str=ts, body=body)
        except ValueError as exc:
            logger.warning("Signature verification failed: %s", exc)
            return JSONResponse(status_code=401, content={"error": str(exc)})

        # 3. Parse + validate Pydantic → 400/422 if fails
        if not body:
            return JSONResponse(status_code=400, content={"error": "Empty body"})
        try:
            raw = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

        try:
            payload = WebhookPayload(**raw)
        except Exception as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

        webhook_id = payload.webhook_id
        event_type = payload.event_type
        payment_id = payload.data.payment_id

        # 4. Atomic idempotency claim via unique constraint
        event = WebhookEvent(
            webhook_id=webhook_id,
            payment_id=payment_id,
            event_type=event_type,
            payload=body.decode("utf-8", errors="replace"),
            processing_status="processing",
            received_at=datetime.now(timezone.utc),
        )
        db.add(event)
        try:
            db.flush()
            is_new = True
        except IntegrityError:
            db.rollback()
            is_new = False

        if not is_new:
            return JSONResponse(
                status_code=200,
                content={"status": "accepted", "webhook_id": webhook_id, "idempotent": True},
            )

        # 5. Look up payment → 404 if not found
        payment = db.get(Payment, payment_id)
        if payment is None:
            db.rollback()
            return JSONResponse(
                status_code=404,
                content={"error": f"Payment '{payment_id}' not found"},
            )

        # 6. Apply state transition
        try:
            new_status = apply_transition(payment.status, event_type)
        except OutOfOrderEventError:
            event.processing_status = "deferred"
            db.commit()
            return JSONResponse(
                status_code=202,
                content={"status": "deferred", "webhook_id": webhook_id},
            )
        except InvalidTransitionError as exc:
            db.rollback()
            return JSONResponse(status_code=422, content={"error": str(exc)})

        # 7. Update payment status + mark event processed
        payment.status = new_status
        payment.updated_at = datetime.now(timezone.utc)
        event.processing_status = "processed"
        event.processed_at = datetime.now(timezone.utc)

        # 8. Commit BEFORE return (fix for race condition)
        db.commit()

        # 9. Attempt deferred replay
        _replay_deferred_events(db, payment)

        # 10. Return 200
        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "webhook_id": webhook_id},
        )

    return application


def _replay_deferred_events(db: Session, payment: Payment) -> None:
    """Attempt to replay deferred events for a payment after a successful transition."""
    deferred = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.payment_id == payment.id,
            WebhookEvent.processing_status == "deferred",
        )
        .all()
    )
    for event in deferred:
        try:
            new_status = apply_transition(payment.status, event.event_type)
        except (InvalidTransitionError, OutOfOrderEventError):
            continue
        payment.status = new_status
        payment.updated_at = datetime.now(timezone.utc)
        event.processing_status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
