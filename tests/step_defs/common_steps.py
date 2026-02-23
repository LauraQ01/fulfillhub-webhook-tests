"""Shared utility constants and helper functions for step definitions.

NOTE: All @given/@when/@then step definitions live in tests/step_defs/conftest.py
so that pytest-bdd can discover them automatically.
This file only contains utility functions and constants.
"""
import json

from tests.helpers.signing import signed_headers

WEBHOOK_SECRET = "test-secret"
WEBHOOK_URL = "/webhooks/yuno"


def _post_webhook(client, payload: dict, headers: dict | None = None) -> object:
    """POST a signed webhook payload to the receiver endpoint."""
    body = json.dumps(payload).encode()
    h = signed_headers(secret=WEBHOOK_SECRET, body=body)
    if headers:
        h.update(headers)
    h["Content-Type"] = "application/json"
    return client.post(WEBHOOK_URL, content=body, headers=h)
