import json
import threading
from typing import Any


def send_concurrent_requests(
    client,
    url: str,
    payload: dict,
    headers: dict,
    n: int = 5,
) -> list[Any]:
    """
    Send n concurrent HTTP POST requests using threads.

    Args:
        client: httpx or starlette TestClient.
        url: Endpoint URL.
        payload: JSON payload dict (same payload for all requests).
        headers: HTTP headers dict.
        n: Number of concurrent requests.

    Returns:
        List of response objects (one per thread).
    """
    results: list[Any] = [None] * n
    body = json.dumps(payload).encode()

    def worker(index: int) -> None:
        try:
            response = client.post(
                url,
                content=body,
                headers={**headers, "Content-Type": "application/json"},
            )
            results[index] = response
        except Exception as exc:  # noqa: BLE001
            results[index] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    return results
