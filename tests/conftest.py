import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.database import get_db
from app.main import create_app
from app.models import Base, Payment

WEBHOOK_SECRET = "test-secret"


@pytest.fixture(scope="function")
def context():
    """Shared mutable dict to pass state between BDD steps within a test."""
    return {}


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite DB per test."""
    engine = create_engine(
        f"sqlite:///file:testdb_{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

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
