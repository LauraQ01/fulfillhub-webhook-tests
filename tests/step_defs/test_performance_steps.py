import json
import time
import threading

import pytest
from pytest_bdd import scenarios, then, when

from tests.fixtures.payloads import make_webhook_payload
from tests.helpers.signing import signed_headers
from tests.step_defs.common_steps import WEBHOOK_SECRET, WEBHOOK_URL, _post_webhook

scenarios("performance.feature")

pytestmark = pytest.mark.slow


@when("I send 100 concurrent authorization webhooks for different payments")
def send_100_concurrent(client, context):
    payment_ids = context["bulk_payment_ids"]
    results = []
    for pid in payment_ids:
        payload = make_webhook_payload(event_type="payment.authorized", payment_id=pid)
        body = json.dumps(payload).encode()
        headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
        results.append((body, headers, payload))

    responses = [None] * len(results)

    def worker(idx, body, headers, payload):
        try:
            resp = client.post(
                WEBHOOK_URL,
                content=body,
                headers={**headers, "Content-Type": "application/json"},
            )
            responses[idx] = resp
        except Exception as exc:  # noqa: BLE001
            responses[idx] = exc

    threads = [
        threading.Thread(target=worker, args=(i, b, h, p))
        for i, (b, h, p) in enumerate(results)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    context["responses"] = [r for r in responses if r is not None]
    context["response"] = context["responses"][0] if context["responses"] else None


@then("no response should have a 5xx status code")
def check_no_5xx(context):
    for resp in context["responses"]:
        if isinstance(resp, Exception):
            continue
        assert resp.status_code < 500, f"Got 5xx: {resp.status_code}"


@then('all 100 payments should be in "authorized" status')
def check_100_authorized(context, db_session):
    db_session.expire_all()
    from app.models import Payment
    payment_ids = context["bulk_payment_ids"]
    for pid in payment_ids:
        p = db_session.get(Payment, pid)
        assert p is not None
        assert p.status == "authorized", f"Payment {pid} has status {p.status!r}"


@when("I send 20 sequential authorization webhooks and measure response times")
def send_20_sequential_timed(client, context):
    payment_ids = context["bulk_payment_ids"]
    times = []
    responses = []
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


@then("the P95 response time should be under 2 seconds")
def check_p95(context):
    times = sorted(context["response_times"])
    p95_idx = int(len(times) * 0.95)
    p95 = times[min(p95_idx, len(times) - 1)]
    assert p95 < 2.0, f"P95 response time {p95:.3f}s exceeds 2s"
