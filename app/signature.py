import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-Yuno-Signature"
TIMESTAMP_HEADER = "X-Yuno-Timestamp"
MAX_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30


def compute_signature(secret: str, timestamp: int, body: bytes) -> str:
    """Compute HMAC-SHA256 signature for the given timestamp and body."""
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str,
    signature: str,
    timestamp_str: str,
    body: bytes,
    max_age: int = MAX_AGE_SECONDS,
    now: float | None = None,
) -> bool:
    """
    Verify HMAC-SHA256 signature.

    Args:
        secret: Webhook secret key.
        signature: The signature from the X-Yuno-Signature header.
        timestamp_str: The timestamp string from X-Yuno-Timestamp header.
        body: Raw request body bytes.
        max_age: Maximum allowed age in seconds (default 300).
        now: Injectable current time for testing. Uses time.time() if None.

    Returns:
        True if signature is valid and not expired.

    Raises:
        ValueError: If signature or timestamp is missing/invalid/expired.
    """
    if not signature:
        raise ValueError("Missing or empty signature header.")

    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid timestamp: {timestamp_str!r}")

    current_time = now if now is not None else time.time()
    age = current_time - timestamp

    if age > max_age:
        raise ValueError(f"Signature expired: {age:.1f}s old (max {max_age}s).")

    if age < -MAX_FUTURE_SKEW_SECONDS:
        raise ValueError(f"Timestamp too far in the future: {-age:.1f}s.")

    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Signature mismatch.")

    return True
