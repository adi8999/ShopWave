"""
conftest.py – shared pytest fixtures for ShopWave backend tests.

Uses an in-memory SQLite database isolated per test session.
"""
import os
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Point to in-memory test DB BEFORE importing the app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-must-be-at-least-32-chars-long"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_PUBLISHABLE_KEY"] = "pk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fake"

from app.database import Base, get_db
from app import models
from app.auth import hash_password
from main import app

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session, dropping first to pick up schema changes."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def db_session(create_tables):
    """
    Provide a fresh DB session per test, rolled back after each test.
    This keeps tests isolated without hitting the filesystem repeatedly.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Override the app dependency
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Reset in-memory rate-limit counters between tests so tests stay isolated
    from app.security.rate_limit import _mem_store, _mem_lock
    with _mem_lock:
        _mem_store.clear()
    yield session

    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    return TestClient(app)


@pytest.fixture
def user(db_session) -> models.User:
    u = models.User(
        name="Test User",
        email="user@test.com",
        hashed_password=hash_password("Password123!"),
        is_admin=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def admin(db_session) -> models.User:
    u = models.User(
        name="Admin User",
        email="admin@test.com",
        hashed_password=hash_password("AdminPass123!"),
        is_admin=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def other_user(db_session) -> models.User:
    u = models.User(
        name="Other User",
        email="other@test.com",
        hashed_password=hash_password("Password123!"),
        is_admin=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def product(db_session) -> models.Product:
    p = models.Product(
        name="Widget",
        description="A test widget",
        price=Decimal("29.99"),
        category="Electronics",
        stock=10,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def low_stock_product(db_session) -> models.Product:
    p = models.Product(
        name="Scarce Widget",
        price=Decimal("49.99"),
        category="Electronics",
        stock=1,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def get_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
