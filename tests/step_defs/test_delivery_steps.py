import time

from pytest_bdd import parsers, scenarios, when, then

from app.models import Payment
from tests.fixtures.payloads import make_webhook_payload
from tests.step_defs.common_steps import _post_webhook

scenarios("delivery.feature")


# Each event type requires the payment to be in a specific state first
_PREREQUISITE_STATUS = {
    "payment.authorized": "pending",
    "payment.captured": "authorized",
    "payment.declined": "pending",
    "payment.settled": "captured",
    "payment.refunded": "captured",
    "payment.chargeback": "settled",
}


@when(parsers.parse('I send a valid "{event_type}" webhook for payment "pay_001"'))
def send_valid_webhook(event_type, client, context, db_session):
    prereq = _PREREQUISITE_STATUS.get(event_type, "pending")
    payment = db_session.get(Payment, "pay_001")
    if payment is None:
        payment = Payment(
            id="pay_001",
            merchant_id="merchant_test",
            amount=10000,
            currency="USD",
            status=prereq,
        )
        db_session.add(payment)
    else:
        payment.status = prereq
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
