import json
import time
import uuid

import pytest
from pytest_bdd import parsers, scenario, scenarios, given, when, then

from app.models import Payment
from tests.fixtures.payloads import make_webhook_payload
from tests.helpers.signing import signed_headers
from tests.step_defs.common_steps import (
    WEBHOOK_SECRET,
    WEBHOOK_URL,
    _post_webhook,
    create_payment,
    create_n_payments,
    check_status_code,
    check_not_5xx,
    all_responses_status,
)

scenarios("delivery.feature")


@pytest.fixture
def context():
    return {}


@when('I send a valid "{event_type}" webhook for payment "pay_001"')
def send_valid_webhook(event_type, client, context, db_session):
    # For the outline, each row gets fresh payment in pending status
    # Ensure pay_001 is in a state that accepts the event
    payment = db_session.get(Payment, "pay_001")
    if payment is None:
        payment = Payment(
            id="pay_001",
            merchant_id="merchant_test",
            amount=10000,
            currency="USD",
            status="pending",
        )
        db_session.add(payment)
        db_session.commit()

    # Reset to pending so each outline row is independent
    payment.status = "pending"
    db_session.commit()

    payload = make_webhook_payload(event_type=event_type, payment_id="pay_001")
    response = _post_webhook(client, payload)
    context["response"] = response
    context["webhook_id"] = payload["webhook_id"]
    context.setdefault("responses", []).append(response)


@then("the response body should contain the webhook_id")
def check_body_webhook_id(context):
    body = context["response"].json()
    assert "webhook_id" in body, f"No webhook_id in body: {body}"


@then("the response Content-Type should be application/json")
def check_content_type(context):
    ct = context["response"].headers.get("content-type", "")
    assert "application/json" in ct, f"Content-Type is {ct!r}"


@when('I send a webhook with event type "payment.exploded" for payment "pay_001"')
def send_unknown_event(client, context):
    payload = make_webhook_payload(event_type="payment.exploded", payment_id="pay_001")
    response = _post_webhook(client, payload)
    context["response"] = response


@when("I send 10 sequential authorization webhooks one by one")
def send_10_sequential(client, context, db_session):
    payment_ids = context["bulk_payment_ids"]
    responses = []
    times = []
    for pid in payment_ids:
        payload = make_webhook_payload(event_type="payment.authorized", payment_id=pid)
        start = time.monotonic()
        resp = _post_webhook(client, payload)
        elapsed = time.monotonic() - start
        responses.append(resp)
        times.append(elapsed)
    context["responses"] = responses
    context["response_times"] = times
    context["response"] = responses[-1]


@then("each response should complete within 5 seconds")
def check_each_within_5s(context):
    for i, t in enumerate(context["response_times"]):
        assert t < 5.0, f"Request {i} took {t:.2f}s (> 5s SLA)"
