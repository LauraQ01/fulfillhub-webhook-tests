import inspect
import json
import time

import pytest
from pytest_bdd import given, scenarios, then, when

from app import signature as sig_module
from app.signature import SIGNATURE_HEADER, TIMESTAMP_HEADER
from tests.fixtures.payloads import make_webhook_payload
from tests.helpers.signing import signed_headers, tampered_headers
from tests.step_defs.common_steps import (
    WEBHOOK_SECRET,
    WEBHOOK_URL,
    create_payment,
    check_status_code,
)

scenarios("signatures.feature")


@pytest.fixture
def context():
    return {}


def _post_raw(client, body: bytes, headers: dict) -> object:
    return client.post(
        WEBHOOK_URL,
        content=body,
        headers={**headers, "Content-Type": "application/json"},
    )


@when('I send a "payment.authorized" webhook with a valid signature for payment "pay_001"')
def send_valid_sig(client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a "payment.authorized" webhook signed with an incorrect secret key')
def send_wrong_secret(client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    body = json.dumps(payload).encode()
    headers = signed_headers(secret="wrong-secret", body=body)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a "payment.authorized" webhook with the body modified after signing')
def send_tampered_body(client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    original_body = json.dumps(payload).encode()
    headers = tampered_headers(secret=WEBHOOK_SECRET, original_body=original_body)
    # Modify the body after signing
    payload["event_type"] = "payment.captured"
    tampered_body = json.dumps(payload).encode()
    response = _post_raw(client, tampered_body, headers)
    context["response"] = response


@when('I send a "payment.authorized" webhook with "{header_scenario}"')
def send_with_header_scenario(header_scenario, client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    headers["Content-Type"] = "application/json"

    if header_scenario == "missing X-Yuno-Signature header":
        headers.pop(SIGNATURE_HEADER, None)
    elif header_scenario == "missing X-Yuno-Timestamp header":
        headers.pop(TIMESTAMP_HEADER, None)
    elif header_scenario == "empty X-Yuno-Signature value":
        headers[SIGNATURE_HEADER] = ""

    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    context["response"] = response


@when('I send a "payment.authorized" webhook with a signature that is 400 seconds old')
def send_expired_sig(client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body, age_seconds=400)
    response = _post_raw(client, body, headers)
    context["response"] = response


@when('I send a "payment.authorized" webhook with a signature that is 299 seconds old')
def send_valid_aged_sig(client, context):
    payload = make_webhook_payload(event_type="payment.authorized", payment_id="pay_001")
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body, age_seconds=299)
    response = _post_raw(client, body, headers)
    context["response"] = response


@then("the signature verification implementation should use hmac.compare_digest")
def check_uses_compare_digest(_):
    source = inspect.getsource(sig_module)
    assert "hmac.compare_digest" in source, (
        "verify_signature does not use hmac.compare_digest"
    )
