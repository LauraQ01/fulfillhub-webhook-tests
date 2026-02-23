# FulfillHub Webhook Test Suite

Automated test suite for FulfillHub's Yuno payment webhook receiver. Built to diagnose and prevent the ~8% silent webhook failure rate caused by DB pool exhaustion, race conditions, out-of-order events, inconsistent HMAC validation, and broken idempotency.

## Stack

- **Python 3.11+**, FastAPI, SQLAlchemy 2.x, SQLite in-memory
- **pytest** + **pytest-bdd** (Gherkin), pytest-timeout, pytest-cov
- **HMAC-SHA256** via stdlib `hashlib`

## Project Structure

```
fulfillhub-webhook-tests/
├── app/                    # Reference webhook receiver (FastAPI)
│   ├── main.py             # POST /webhooks/yuno endpoint
│   ├── models.py           # ORM: Payment, WebhookEvent
│   ├── database.py         # Engine/session factory
│   ├── schemas.py          # Pydantic validation
│   ├── state_machine.py    # Payment state transitions
│   └── signature.py        # HMAC-SHA256 verification
└── tests/
    ├── features/           # Gherkin feature files (6 features)
    ├── step_defs/          # pytest-bdd step implementations
    ├── fixtures/           # Payload factory functions
    └── helpers/            # Signing & concurrency utilities
```

## Quick Start

```bash
# 1. Clone and enter
git clone <repo-url>
cd fulfillhub-webhook-tests

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run full test suite
pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

# 5. Run only core requirements (fast)
pytest tests/step_defs/test_delivery_steps.py \
       tests/step_defs/test_idempotency_steps.py \
       tests/step_defs/test_ordering_steps.py -v

# 6. Skip slow performance tests
pytest tests/ -m "not slow" -v
```

## Test Coverage

| Feature File | Scenarios | Covers |
|---|---|---|
| `delivery.feature` | 8 | HTTP responses, event types, SLA |
| `idempotency.feature` | 5 | Duplicate detection, race conditions |
| `ordering.feature` | 14 | State machine, deferred replay |
| `signatures.feature` | 7 | HMAC-SHA256, replay attacks |
| `performance.feature` | 2 | Concurrency, P95 latency |
| `negative.feature` | 13 | Malformed payloads, SQL injection |

**Total: 33 scenarios, expected >= 80% coverage on `app/`**

## Key Design Decisions

- **Atomic idempotency**: `UNIQUE INDEX` on `webhook_id` + `INSERT ... flush()` catches `IntegrityError` before processing -- prevents double-spend on concurrent retries.
- **Commit before return**: `db.commit()` always precedes `return Response(...)` -- fixes the production race condition where 200 OK was returned before the DB write completed.
- **Deferred replay**: Out-of-order events are stored as `deferred` and replayed automatically after each successful transition.
- **Injectable `now`**: `verify_signature(now=...)` accepts a timestamp override -- enables deterministic tests without monkeypatching.
- **Isolated DB per test**: Each test gets a unique `sqlite:///file:testdb_{uuid}?mode=memory&cache=shared&uri=true` -- no shared state between concurrent tests.

## Running the Receiver Locally

```bash
uvicorn app.main:create_app --factory --reload
# POST http://localhost:8000/webhooks/yuno
```
