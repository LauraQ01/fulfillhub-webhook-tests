import uuid


def make_webhook_payload(
    event_type: str,
    payment_id: str,
    webhook_id: str | None = None,
    merchant_id: str = "merchant_test",
    amount: int = 10000,
    currency: str = "USD",
    **overrides,
) -> dict:
    """Build a valid webhook payload dict."""
    payload = {
        "webhook_id": webhook_id or f"wh-{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "data": {
            "payment_id": payment_id,
            "merchant_id": merchant_id,
            "amount": amount,
            "currency": currency,
        },
    }
    payload.update(overrides)
    return payload


def make_payment_record(
    payment_id: str = "pay_001",
    merchant_id: str = "merchant_test",
    amount: int = 10000,
    currency: str = "USD",
    status: str = "pending",
) -> dict:
    """Build a payment record dict suitable for direct DB insertion."""
    return {
        "id": payment_id,
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": currency,
        "status": status,
    }
