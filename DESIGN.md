# FulfillHub Webhook Test Strategy

## 1. Problem Statement

FulfillHub experienced ~8% silent webhook failures in production. Root cause analysis identified five distinct failure modes:

| # | Failure Mode | Impact |
|---|---|---|
| 1 | DB pool exhaustion causing timeouts | Webhooks silently dropped |
| 2 | Race condition: 200 OK returned before DB commit | Payment state corrupted |
| 3 | Out-of-order events crashing the state machine | Unhandled 500 errors |
| 4 | Inconsistent HMAC signature validation | Forged webhooks accepted |
| 5 | Broken idempotency on Yuno retries | Payments processed twice |

## 2. Test Strategy

### 2.1 Framework Choice: pytest-bdd (Gherkin)

Gherkin (`.feature` files) was chosen over plain pytest for three reasons:

1. **Business readability**: Non-technical stakeholders (payments team, compliance) can read and validate scenarios without understanding Python.
2. **Reusable steps**: `common_steps.py` centralizes shared Given/When/Then definitions, reducing duplication across 6 feature files.
3. **Living documentation**: Feature files serve as the authoritative specification for webhook behavior.

### 2.2 Test Architecture

```
conftest.py          <- Fixtures (DB isolation, app factory, client)
common_steps.py      <- Shared steps (used in >= 2 features)
test_X_steps.py      <- Feature-specific step implementations
fixtures/payloads.py <- Payload factory functions
helpers/signing.py   <- HMAC header generation
helpers/concurrency.py <- Thread-based concurrent request runner
```

### 2.3 DB Isolation Strategy

Each test function receives a **unique in-memory SQLite database**:

```python
f"sqlite:///file:testdb_{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"
```

This prevents test pollution in concurrent execution and avoids the overhead of file-based SQLite cleanup.

## 3. Test Categories

### Core Requirements

#### Feature 1: Webhook Delivery (`delivery.feature`)
Validates that all 6 canonical Yuno event types return HTTP 200 with correct Content-Type and webhook_id in the response body. Also verifies the 5-second SLA for sequential processing.

**Key scenarios**: Valid event types (Outline x 6), unknown event rejection, SLA timing.

#### Feature 2: Idempotency (`idempotency.feature`)
Verifies that duplicate webhooks (same `webhook_id`) are processed exactly once, even under concurrent load. Tests the atomic `INSERT + IntegrityError` pattern and confirms the DB commit happens before the 200 response.

**Key scenarios**: Duplicate handling, DB persistence before 200, concurrent race (5 threads), Yuno retry returns 200 not 409.

#### Feature 3: Out-of-Order Events (`ordering.feature`)
Tests the deferred replay mechanism: events arriving before their prerequisites are stored as `deferred` and replayed automatically once the missing transitions complete.

**Key scenarios**: Full lifecycle in reverse order -> reaches `settled`, all valid transitions (Outline x 8), invalid terminal states (Outline x 4).

### Stretch Goals

#### Feature 4: Signature Verification (`signatures.feature`)
Validates HMAC-SHA256 verification including timing attack prevention (`hmac.compare_digest`), expired signatures (> 300s), tampered bodies, and missing headers.

**Key scenarios**: Wrong secret -> 401, tampered body -> 401, expired (400s) -> 401, valid aged (299s) -> 200, `compare_digest` code inspection.

#### Feature 5: Performance (`performance.feature`)
Stress tests with 100 concurrent webhooks for different payments and measures P95 response time for 20 sequential requests.

**Key scenarios**: 100 concurrent -> no 5xx, P95 < 2s.

#### Feature 6: Negative Testing (`negative.feature`)
Exhaustive malformed input testing: missing fields, wrong types, SQL injection, 10MB payloads, 1000-level nested JSON, unicode merchant IDs.

**Key scenarios**: Missing fields (Outline x 6), wrong types (Outline x 2), invalid amounts (Outline x 2), SQL injection, oversized, deeply nested, invalid bodies (Outline x 3).

## 4. Fixes Implemented in Reference App

### Fix 1: Atomic Idempotency (Race Condition)
```python
db.add(event)
try:
    db.flush()  # Raises IntegrityError if webhook_id already exists
    is_new = True
except IntegrityError:
    db.rollback()
    is_new = False
```

### Fix 2: Commit Before Return
```python
db.commit()  # ALWAYS before return
return JSONResponse(status_code=200, content={...})
```

### Fix 3: Deferred Replay
```python
# After successful transition:
_replay_deferred_events(db, payment)
# Retries all 'deferred' events for this payment recursively
```

### Fix 4: Injectable Timestamp
```python
def verify_signature(..., now: float | None = None):
    current_time = now if now is not None else time.time()
```

### Fix 5: Constant-Time Comparison
```python
if not hmac.compare_digest(expected, signature):
    raise ValueError("Signature mismatch.")
```

## 5. Coverage Goals

| Module | Target |
|---|---|
| `app/main.py` | >= 85% |
| `app/state_machine.py` | 100% |
| `app/signature.py` | >= 90% |
| `app/models.py` | >= 70% |
| **Overall** | **>= 80%** |
