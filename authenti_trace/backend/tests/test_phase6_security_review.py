import logging

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import security
from app.database.database import get_db
from app.main import app
from app.models.ledger import Base
from app.services import media_service


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 't.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine)

    async def override():
        async with factory() as session:
            yield session

    security.limiter.hits.clear()
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    security.limiter.hits.clear()
    await engine.dispose()


def test_server_refuses_to_start_without_keys_when_auth_is_required(monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("REQUIRE_API_KEYS", "true")
    with pytest.raises(RuntimeError, match="Refusing to start"):
        security.check_startup()


def test_startup_is_fine_with_keys_and_only_warns_in_development(monkeypatch, caplog):
    monkeypatch.setenv("REQUIRE_API_KEYS", "true")
    monkeypatch.setenv("API_KEYS", "alice:k")
    security.check_startup()  # no error
    monkeypatch.delenv("API_KEYS")
    monkeypatch.delenv("REQUIRE_API_KEYS")
    with caplog.at_level(logging.WARNING):
        security.check_startup()
    assert "authentication is OFF" in caplog.text


def test_the_ledger_audit_has_its_own_strict_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_HEAVY_PER_MINUTE", "2")
    codes = [client.get("/api/v1/dashboard/audit").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.get("/api/v1/dashboard/metrics").status_code == 200  # cheap endpoints keep their own budget


def test_image_size_default_is_conservative():
    assert media_service.MAX_IMAGE_PIXELS == 25_000_000
