"""
integration/test_postgres_redis.py – Real PostgreSQL & Redis integration tests.

Requires:
  • POSTGRES_TEST_URL (e.g. postgresql://postgres:postgres@localhost:5432/shopwave_test)
  • REDIS_TEST_URL    (e.g. redis://localhost:6379/0)

Skips cleanly with an explicit reason when those services are not configured.
In GitHub Actions CI, both PostgreSQL and Redis service containers are started
and these tests run automatically.
"""
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
REDIS_TEST_URL = os.getenv("REDIS_TEST_URL")


@pytest.mark.skipif(not POSTGRES_TEST_URL, reason="POSTGRES_TEST_URL not set; skipping PostgreSQL integration tests")
class TestPostgresIntegration:
    def test_alembic_upgrade_head_on_clean_postgres(self):
        """Verify Alembic migrations run cleanly from scratch on PostgreSQL."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = os.environ.copy()
        env["DATABASE_URL"] = POSTGRES_TEST_URL
        env.setdefault("SECRET_KEY", "ci-postgres-test-secret-key-at-least-32-chars")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"

    def test_concurrent_postgres_checkout_cannot_oversell_last_item(self):
        """
        True multithreaded PostgreSQL checkout race test exercising SELECT ... FOR UPDATE.
        5 users attempt simultaneous checkout for a product with stock=1.
        Exactly 1 must succeed (201) and 4 must fail (409), leaving stock=0.
        """
        from app import models
        from app.auth import create_access_token, hash_password
        from app.database import get_db
        from main import app

        pg_engine = create_engine(POSTGRES_TEST_URL, pool_size=10, max_overflow=10)
        PgSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

        # Ensure schema is migrated
        self.test_alembic_upgrade_head_on_clean_postgres()

        db = PgSession()
        tag = uuid.uuid4().hex[:8]
        product = models.Product(
            name=f"PG Race Item {tag}",
            price=Decimal("19.99"),
            category="Electronics",
            stock=1,
            is_active=True,
        )
        db.add(product)
        db.flush()

        users = []
        tokens = []
        for i in range(5):
            u = models.User(
                name=f"RaceUser{i}",
                email=f"race_{tag}_{i}@test.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add(u)
            db.flush()
            db.add(models.CartItem(user_id=u.id, product_id=product.id, quantity=1))
            users.append(u)
            tokens.append(create_access_token({"sub": str(u.id)}, token_version=u.token_version))
        db.commit()
        product_id = product.id
        user_ids = [u.id for u in users]
        db.close()

        def override_get_db():
            s = PgSession()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        payload = {
            "shipping_name": "Race Buyer",
            "shipping_address": "100 Lock Ave",
            "shipping_city": "PGCity",
            "shipping_zip": "10001",
        }

        def attempt_checkout(tok: str) -> int:
            with TestClient(app) as c:
                r = c.post(
                    "/api/orders/checkout",
                    json=payload,
                    headers={"Authorization": f"Bearer {tok}"},
                )
                return r.status_code

        try:
            with ThreadPoolExecutor(max_workers=5) as pool:
                statuses = list(pool.map(attempt_checkout, tokens))
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert statuses.count(201) == 1, f"Expected exactly 1 success, got {statuses}"
        assert statuses.count(409) == 4, f"Expected 4 conflicts, got {statuses}"

        verify_db = PgSession()
        try:
            refreshed = verify_db.query(models.Product).filter(models.Product.id == product_id).first()
            assert refreshed.stock == 0
            orders = verify_db.query(models.Order).filter(models.Order.user_id.in_(user_ids)).all()
            assert len(orders) == 1
        finally:
            verify_db.close()
            pg_engine.dispose()


@pytest.mark.skipif(not REDIS_TEST_URL, reason="REDIS_TEST_URL not set; skipping Redis integration tests")
class TestRedisRateLimitIntegration:
    def test_redis_sliding_window_enforces_limit_and_429(self, monkeypatch):
        import redis
        import app.security.rate_limit as rl

        client = redis.from_url(REDIS_TEST_URL, decode_responses=True)
        client.ping()
        monkeypatch.setattr(rl, "_redis_client", client)

        prefix = f"rl:it:{uuid.uuid4().hex[:8]}"
        limiter = rl.RateLimiter(requests=3, window_seconds=30, key_prefix=prefix)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("10.0.0.42", 12345),
        }
        req = Request(scope)

        limiter(req)
        limiter(req)
        limiter(req)
        with pytest.raises(HTTPException) as exc:
            limiter(req)
        assert exc.value.status_code == 429
        assert exc.value.headers.get("Retry-After") == "30"
