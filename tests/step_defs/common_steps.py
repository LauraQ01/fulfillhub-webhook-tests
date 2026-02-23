import json
import uuid

import pytest
from pytest_bdd import given, then, when

from app.models import Payment, WebhookEvent
from tests.fixtures.payloads import make_webhook_payload
from tests.helpers.signing import signed_headers

WEBHOOK_SECRET = "test-secret"
WEBHOOK_URL = "/webhooks/yuno"


def _post_webhook(client, payload: dict, headers: dict | None = None) -> object:
    body = json.dumps(payload).encode()
    h = signed_headers(secret=WEBHOOK_SECRET, body=body)
    if headers:
        h.update(headers)
    h["Content-Type"] = "application/json"
    return client.post(WEBHOOK_URL, content=body, headers=h)


# ── Given steps ────────────────────────────────────────────────────────────────

@given('a payment "{pid}" exists in "{status}" status')
def create_payment(pid, status, db_session):
    existing = db_session.get(Payment, pid)
    if existing:
        existing.status = status
        db_session.commit()
        return existing
    payment = Payment(
        id=pid,
        merchant_id="merchant_test",
        amount=10000,
        currency="USD",
        status=status,
    )
    db_session.add(payment)
    db_session.commit()
    return payment


@given("{n:d} payments exist in \"{status}\" status")
def create_n_payments(n, status, db_session, context):
    payment_ids = []
    for i in range(n):
        pid = f"pay_bulk_{uuid.uuid4().hex[:8]}"
        payment = Payment(
            id=pid,
            merchant_id="merchant_test",
            amount=10000,
            currency="USD",
            status=status,
        )
        db_session.add(payment)
        payment_ids.append(pid)
    db_session.commit()
    context["bulk_payment_ids"] = payment_ids


# ── When steps ─────────────────────────────────────────────────────────────────

@when('I send a "{event_type}" webhook for payment "{pid}"')
def send_webhook(event_type, pid, client, context):
    payload = make_webhook_payload(event_type=event_type, payment_id=pid)
    response = _post_webhook(client, payload)
    context["response"] = response
    context.setdefault("responses", []).append(response)


# ── Then steps ─────────────────────────────────────────────────────────────────

@then("the response status should be {code:d}")
def check_status_code(code, context):
    assert context["response"].status_code == code, (
        f"Expected {code}, got {context['response'].status_code}: "
        f"{context['response'].text}"
    )


@then("the response status should not be a 5xx error")
def check_not_5xx(context):
    assert context["response"].status_code < 500, (
        f"Got 5xx: {context['response'].status_code}: {context['response'].text}"
    )


@then('the payment "{pid}" status should be "{expected}"')
def check_payment_status(pid, expected, db_session):
    db_session.expire_all()
    payment = db_session.get(Payment, pid)
    assert payment is not None, f"Payment {pid!r} not found"
    assert payment.status == expected, (
        f"Expected status {expected!r}, got {payment.status!r}"
    )


@then("all responses should have status {code:d}")
def all_responses_status(code, context):
    for resp in context.get("responses", []):
        assert resp.status_code == code, (
            f"Expected {code}, got {resp.status_code}: {resp.text}"
        )


@then("all responses should have a 2xx status")
def all_responses_2xx(context):
    for resp in context.get("responses", []):
        assert 200 <= resp.status_code < 300, (
            f"Got non-2xx: {resp.status_code}: {resp.text}"
        )
