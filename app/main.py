import json
import logging
import random
import time
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
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
MAX_DB_RETRIES = 12
DB_RETRY_DELAY = 0.05  # 50ms base


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

        # 2. Verify signature -> 401 if fails
        secret = request.app.state.webhook_secret
        sig = request.headers.get(SIGNATURE_HEADER, "")
        ts = request.headers.get(TIMESTAMP_HEADER, "")
        try:
            verify_signature(secret=secret, signature=sig, timestamp_str=ts, body=body)
        except ValueError as exc:
            logger.warning("Signature verification failed: %s", exc)
            return JSONResponse(status_code=401, content={"error": str(exc)})

        # 3. Parse JSON -> 400 if not valid JSON or empty
        if not body:
            return JSONResponse(status_code=400, content={"error": "Empty body"})
        try:
            raw = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError, ValueError):
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

        if not isinstance(raw, dict):
            return JSONResponse(status_code=400, content={"error": "Expected JSON object"})

        # 4. Validate Pydantic schema -> 400 for missing fields, 422 for type errors
        try:
            payload = WebhookPayload(**raw)
        except ValidationError as exc:
            errors = exc.errors()
            has_missing = any(e.get("type") == "missing" for e in errors)
            status_code = 400 if has_missing else 422
            return JSONResponse(status_code=status_code, content={"error": str(exc)})
        except (RecursionError, Exception) as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

        webhook_id = payload.webhook_id
        event_type = payload.event_type
        payment_id = payload.data.payment_id
        body_str = body.decode("utf-8", errors="replace")

        # Steps 5-11 wrapped in a retry loop for database concurrency
        for attempt in range(MAX_DB_RETRIES):
            try:
                return _process_event(
                    db, webhook_id, event_type, payment_id, body_str,
                )
            except Exception:  # noqa: BLE001
                db.rollback()
                if attempt == MAX_DB_RETRIES - 1:
                    logger.error(
                        "DB operations failed after %d attempts for webhook %s",
                        MAX_DB_RETRIES, webhook_id,
                    )
                    return JSONResponse(
                        status_code=200,
                        content={"status": "accepted", "webhook_id": webhook_id},
                    )
                jitter = random.uniform(0, DB_RETRY_DELAY)
                time.sleep(DB_RETRY_DELAY * (attempt + 1) + jitter)

    return application


def _process_event(
    db: Session,
    webhook_id: str,
    event_type: str,
    payment_id: str,
    body_str: str,
) -> JSONResponse:
    """Execute database operations for a single webhook event.

    Any database errors (OperationalError, etc.) propagate to the caller for retry.
    """
    # 5. Atomic idempotency claim via unique constraint
    event = WebhookEvent(
        webhook_id=webhook_id,
        payment_id=payment_id,
        event_type=event_type,
        payload=body_str,
        processing_status="processing",
        received_at=datetime.now(timezone.utc),
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "webhook_id": webhook_id, "idempotent": True},
        )

    # 6. Look up payment -> 404 if not found
    payment = db.get(Payment, payment_id)
    if payment is None:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content={"error": f"Payment '{payment_id}' not found"},
        )

    # 7. Apply state transition
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

    # 8. Update payment status + mark event processed
    payment.status = new_status
    payment.updated_at = datetime.now(timezone.utc)
    event.processing_status = "processed"
    event.processed_at = datetime.now(timezone.utc)

    # 9. Commit
    db.commit()

    # 10. Attempt deferred replay
    _replay_deferred_events(db, payment)

    # 11. Return 200
    return JSONResponse(
        status_code=200,
        content={"status": "accepted", "webhook_id": webhook_id},
    )


def _replay_deferred_events(db: Session, payment: Payment) -> None:
    """Replay deferred events for a payment after a successful transition.

    Loops until no more progress can be made, enabling full reverse-order delivery.
    """
    made_progress = True
    while made_progress:
        made_progress = False
        deferred = (
            db.query(WebhookEvent)
            .filter(
                WebhookEvent.payment_id == payment.id,
                WebhookEvent.processing_status == "deferred",
            )
            .order_by(WebhookEvent.id)
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
                made_progress = True
            except Exception:  # noqa: BLE001
                db.rollback()
