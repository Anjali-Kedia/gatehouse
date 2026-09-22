import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import gatehouse.models  # noqa: F401  registers tables on SQLModel.metadata


def _fresh_sqlite_engine():
    # StaticPool: an in-memory SQLite DB is per-connection, and FastAPI's sync
    # endpoints run in a threadpool worker thread — without a single shared
    # connection, each request could land on its own empty, table-less DB.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session():
    engine = _fresh_sqlite_engine()
    with Session(engine) as session:
        yield session


@pytest.fixture()
def sandbox_session_id():
    return uuid.uuid4().hex


@pytest.fixture()
def test_engine():
    return _fresh_sqlite_engine()


@pytest.fixture()
def client(test_engine):
    """A TestClient wired to its own isolated in-memory DB (`test_engine`) via
    FastAPI's standard dependency-override mechanism. JEV_ADAPTER stays at its
    .env default ("mock"), so these tests never touch the real API. Tests that
    need to directly inspect or mutate rows (e.g. to simulate an approval aging
    past its expiry without sleeping) can open their own `Session(test_engine)`.
    """
    from api.main import app
    from gatehouse.db import get_session

    def _override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        # Deliberately not `with TestClient(...)`: that runs the app's lifespan
        # (init_db against the *real* default engine), which we don't need —
        # test_engine already has its own tables.
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
