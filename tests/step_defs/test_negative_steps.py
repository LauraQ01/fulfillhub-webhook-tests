import json

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.fixtures.payloads import make_webhook_payload
from tests.helpers.signing import signed_headers
from tests.step_defs.common_steps import (
    WEBHOOK_SECRET,
    WEBHOOK_URL,
    _post_webhook,
    create_payment,
    check_status_code,
    check_not_5xx,
)

scenarios("negative.feature")


@pytest.fixture
def context():
    return {}


def _post_raw(client, body: bytes, headers: dict) -> object:
    return client.post(
        WEBHOOK_URL,
        content=body,
        headers={**headers, "Content-Type": "application/json"},
    )


@when('I send a "payment.authorized" webhook for payment "{pid}" without the "{field}" field')
def send_missing_field(pid, field, client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id=pid)

    if field == "payment_id":
        del payload["data"]["payment_id"]
    elif field == "amount":
        del payload["data"]["amount"]
    elif field == "currency":
        del payload["data"]["currency"]
    elif field == "data":
        del payload["data"]
    else:
        del payload[field]

    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a webhook with field "{field}" set to a "{wrong_type}" value')
def send_wrong_type(field, wrong_type, client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")

    if field == "amount" and wrong_type == "string":
        payload["data"]["amount"] = "not-a-number"
    elif field == "webhook_id" and wrong_type == "integer":
        payload["webhook_id"] = 12345

    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a webhook with amount value "{amount_value}" for payment "pay_001"')
def send_invalid_amount(amount_value, client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    payload["data"]["amount"] = int(amount_value)
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a webhook with payment_id set to "\'; DROP TABLE payments; --"')
def send_sql_injection(client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id="'; DROP TABLE payments; --",
    )
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when("I send a webhook request with a 10 megabyte payload")
def send_oversized(client, context):
    junk = "x" * (10 * 1024 * 1024)
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    payload["junk"] = junk
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@then("the response status should be 413 or 422")
def check_413_or_422(context):
    sc = context["response"].status_code
    assert sc in (413, 422), f"Expected 413 or 422, got {sc}: {context['response'].text}"


@when("I send a webhook with 1000 levels of nested JSON")
def send_deeply_nested(client, context):
    nested: dict = {}
    current = nested
    for _ in range(999):
        current["child"] = {}
        current = current["child"]
    current["value"] = "deep"

    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    payload["nested"] = nested
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a request with a "{body_description}" as the body')
def send_invalid_body(body_description, client, context):
    ts = __import__("time").time()
    from app.signature import compute_signature, SIGNATURE_HEADER, TIMESTAMP_HEADER

    if body_description == "non-JSON text":
        body = b"this is not json"
    elif body_description == "empty body":
        body = b""
    elif body_description == "empty JSON {}":
        body = b"{}"
    else:
        body = b""

    ts_int = int(ts)
    sig = compute_signature(WEBHOOK_SECRET, ts_int, body)
    headers = {
        SIGNATURE_HEADER: sig,
        TIMESTAMP_HEADER: str(ts_int),
        "Content-Type": "application/json",
    }
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    context["response"] = response


@then("the response status should be 400 or 422")
def check_400_or_422(context):
    sc = context["response"].status_code
    assert sc in (400, 422), f"Expected 400 or 422, got {sc}: {context['response'].text}"


@when("I send a valid webhook with unicode and emoji characters in the merchant_id")
def send_unicode(client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id="pay_001",
        merchant_id="商店🌟emoji_merchant",
    )
    response = _post_webhook(client, payload)
    context["response"] = response


@when('I send a "payment.authorized" webhook for non-existent payment "pay_NONEXISTENT"')
def send_nonexistent_payment(client, context):
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id="pay_NONEXISTENT",
    )
    response = _post_webhook(client, payload)
    context["response"] = response
