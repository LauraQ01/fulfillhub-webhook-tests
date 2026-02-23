import pytest
from pytest_bdd import given, scenarios, then, when

from app.models import WebhookEvent
from tests.fixtures.payloads import make_webhook_payload
from tests.step_defs.common_steps import (
    _post_webhook,
    create_payment,
    check_status_code,
    check_not_5xx,
    check_payment_status,
)

scenarios("ordering.feature")


@pytest.fixture
def context():
    return {}


@when('I send a "{event_type}" webhook before its prerequisite event')
def send_out_of_order(event_type, client, context):
    payload = make_webhook_payload(event_type=event_type, payment_id="pay_001")
    response = _post_webhook(client, payload)
    context["response"] = response


@then("all {n:d} events should be stored in the database")
def check_n_events(n, db_session):
    db_session.expire_all()
    events = db_session.query(WebhookEvent).filter(
        WebhookEvent.payment_id == "pay_001"
    ).all()
    assert len(events) == n, f"Expected {n} events, found {len(events)}"


@when("I send the full payment lifecycle in reverse order for payment \"pay_001\"")
def send_reversed_lifecycle(client, context, db_session):
    # Full lifecycle: pending→authorized→captured→settled
    # Reverse delivery: settled, captured, authorized
    events_reversed = [
        "payment.settled",
        "payment.captured",
        "payment.authorized",
    ]
    responses = []
    for event_type in events_reversed:
        payload = make_webhook_payload(event_type=event_type, payment_id="pay_001")
        response = _post_webhook(client, payload)
        responses.append(response)
    context["responses"] = responses
    context["response"] = responses[-1]


@then("the response status should be 200 or 202")
def check_200_or_202(context):
    sc = context["response"].status_code
    assert sc in (200, 202), f"Expected 200 or 202, got {sc}: {context['response'].text}"
