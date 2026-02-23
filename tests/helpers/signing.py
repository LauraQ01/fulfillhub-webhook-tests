import time

from app.signature import compute_signature, SIGNATURE_HEADER, TIMESTAMP_HEADER


def signed_headers(
    secret: str,
    body: bytes,
    timestamp: int | None = None,
    age_seconds: int = 0,
) -> dict[str, str]:
    """
    Build HTTP headers with a valid HMAC-SHA256 signature.

    Args:
        secret: Webhook secret.
        body: Raw request body bytes.
        timestamp: Override timestamp (unix seconds). Defaults to now - age_seconds.
        age_seconds: How old to make the signature (positive = in the past).

    Returns:
        Dict with X-Yuno-Signature and X-Yuno-Timestamp headers.
    """
    if timestamp is None:
        timestamp = int(time.time()) - age_seconds
    sig = compute_signature(secret, timestamp, body)
    return {
        SIGNATURE_HEADER: sig,
        TIMESTAMP_HEADER: str(timestamp),
    }


def tampered_headers(
    secret: str,
    original_body: bytes,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Return headers signed for original_body but will be sent with different body."""
    if timestamp is None:
        timestamp = int(time.time())
    sig = compute_signature(secret, timestamp, original_body)
    return {
        SIGNATURE_HEADER: sig,
        TIMESTAMP_HEADER: str(timestamp),
    }
