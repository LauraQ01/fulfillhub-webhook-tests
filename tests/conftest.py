import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.database import get_db
from app.main import create_app
from app.models import Base, Payment

WEBHOOK_SECRET = "test-secret"


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite DB per test."""
    engine = create_engine(
        f"sqlite:///file:testdb_{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def app(db_engine):
    """Create a FastAPI app with isolated DB per test."""
    application = create_app(webhook_secret=WEBHOOK_SECRET)
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app):
    """HTTP test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Raw DB session for direct inspection/insertion."""
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="function")
def pending_payment(db_session):
    """Insert a payment in 'pending' status directly into DB."""
    payment = Payment(
        id="pay_001",
        merchant_id="merchant_test",
        amount=10000,
        currency="USD",
        status="pending",
    )
    db_session.add(payment)
    db_session.commit()
    return payment


@pytest.fixture(scope="function")
def authorized_payment(client, db_session):
    """Create a payment in 'authorized' status by sending a real webhook."""
    import json
    import time

    from tests.helpers.signing import signed_headers
    from tests.fixtures.payloads import make_webhook_payload

    # First insert pending payment
    payment = Payment(
        id="pay_auth_001",
        merchant_id="merchant_test",
        amount=10000,
        currency="USD",
        status="pending",
    )
    db_session.add(payment)
    db_session.commit()

    # Then send authorization webhook
    payload = make_webhook_payload(
        event_type="payment.authorized",
        payment_id="pay_auth_001",
        webhook_id=f"wh-auth-{uuid.uuid4().hex[:8]}",
    )
    body = json.dumps(payload).encode()
    headers = signed_headers(secret=WEBHOOK_SECRET, body=body)
    headers["Content-Type"] = "application/json"
    client.post("/webhooks/yuno", content=body, headers=headers)

    db_session.expire_all()
    return db_session.get(Payment, "pay_auth_001")
