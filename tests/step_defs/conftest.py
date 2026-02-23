"""Shared BDD step definitions for all feature files.

Step definitions live here (not in common_steps.py) because pytest-bdd 7.x
registers step fixtures in the caller module's locals via get_caller_module_locals().
Only conftest.py modules are auto-discovered by pytest, so steps MUST be defined
here for pytest-bdd to find them across all test files in this directory.

IMPORTANT: All parametric steps use parsers.parse() — plain strings use
the 'string' parser which does exact matching and treats {param} as literal.
"""
import json
import uuid

from pytest_bdd import given, parsers, then, when

from app.models import Payment, WebhookEvent
from tests.fixtures.payloads import make_webhook_payload
from tests.step_defs.common_steps import _post_webhook


# ── Given ──────────────────────────────────────────────────────────────────────

@given(parsers.parse('a payment "{pid}" exists in "{status}" status'))
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


@given(parsers.parse('{n:d} payments exist in "{status}" status'))
def create_n_payments(n, status, db_session, context):
    payment_ids = []
    for _ in range(n):
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


# ── When ───────────────────────────────────────────────────────────────────────

@when(parsers.parse('I send a "{event_type}" webhook for payment "{pid}"'))
def send_webhook(event_type, pid, client, context):
    payload = make_webhook_payload(event_type=event_type, payment_id=pid)
    response = _post_webhook(client, payload)
    context["response"] = response
    context.setdefault("responses", []).append(response)


# ── Then ───────────────────────────────────────────────────────────────────────

@then(parsers.parse("the response status should be {code:d}"))
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


@then(parsers.parse('the payment "{pid}" status should be "{expected}"'))
def check_payment_status(pid, expected, db_session):
    db_session.expire_all()
    payment = db_session.get(Payment, pid)
    assert payment is not None, f"Payment {pid!r} not found"
    assert payment.status == expected, (
        f"Expected status {expected!r}, got {payment.status!r}"
    )


@then(parsers.parse("all responses should have status {code:d}"))
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
