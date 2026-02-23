import json

from pytest_bdd import given, parsers, scenarios, then, when

from app.models import WebhookEvent
from tests.fixtures.payloads import make_webhook_payload
from tests.helpers.concurrency import send_concurrent_requests
from tests.helpers.signing import signed_headers
from tests.step_defs.common_steps import WEBHOOK_SECRET, WEBHOOK_URL, _post_webhook

scenarios("idempotency.feature")


@when(parsers.parse('I send a "payment.authorized" webhook with id "{wid}" for payment "{pid}"'))
def send_with_id(wid, pid, client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id=pid,
        webhook_id=wid,
    )
    response = _post_webhook(client, payload)
    context["response"] = response
    context.setdefault("responses", []).append(response)
    context["last_payload"] = payload
    context["last_wid"] = wid


@when(parsers.parse('I send the same webhook with id "{wid}" again'))
def send_same_again(wid, client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id="pay_001",
        webhook_id=wid,
    )
    response = _post_webhook(client, payload)
    context["response"] = response
    context.setdefault("responses", []).append(response)


@then("both responses should have status 200")
def both_200(context):
    for resp in context["responses"]:
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"


@then(parsers.parse('there should be exactly 1 processed event for webhook "{wid}" in the database'))
def exactly_one_event(wid, db_session):
    db_session.expire_all()
    events = (
        db_session.query(WebhookEvent)
        .filter(WebhookEvent.webhook_id == wid)
        .all()
    )
    assert len(events) == 1, f"Expected 1 event for {wid!r}, found {len(events)}"


@then(parsers.parse('event "{wid}" should exist in the database with processing_status "{status}"'))
def event_exists_with_status(wid, status, db_session):
    db_session.expire_all()
    event = (
        db_session.query(WebhookEvent)
        .filter(WebhookEvent.webhook_id == wid)
        .first()
    )
    assert event is not None, f"No event with webhook_id={wid!r}"
    assert event.processing_status == status, (
        f"Expected processing_status={status!r}, got {event.processing_status!r}"
    )


@when(parsers.parse('I send 5 concurrent requests with webhook id "{wid}" for payment "{pid}"'))
def send_concurrent(wid, pid, client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id=pid,
        webhook_id=wid,
    )
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    results = send_concurrent_requests(
        client=client,
        url=WEBHOOK_URL,
        payload=payload,
        headers=headers,
        n=5,
    )
    context["responses"] = [r for r in results if not isinstance(r, Exception)]
    context["response"] = context["responses"][0] if context["responses"] else None


@given(parsers.parse('I successfully sent a "payment.authorized" webhook with id "{wid}" for payment "{pid}"'))
def pre_send_webhook(wid, pid, client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id=pid,
        webhook_id=wid,
    )
    response = _post_webhook(client, payload)
    assert response.status_code == 200
    context["pre_response"] = response


@when(parsers.parse('I send the same webhook with id "{wid}" again simulating a Yuno retry'))
def retry_send(wid, client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id="pay_001",
        webhook_id=wid,
    )
    response = _post_webhook(client, payload)
    context["response"] = response


@then("the response body should indicate it was an idempotent response")
def check_idempotent_flag(context):
    body = context["response"].json()
    assert body.get("idempotent") is True, f"Expected idempotent=true in body: {body}"
