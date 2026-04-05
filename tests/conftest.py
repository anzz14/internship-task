import os
import sys
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


# Pytest is typically run from the finance_app/ directory (see README). Since the
# package directory is `finance_app/` itself (not `finance_app/finance_app/`), we
# need the repo root on sys.path for `import finance_app` to work.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture(scope="session", autouse=True)
def _load_env_for_tests() -> None:
    """Load dotenv via the app's supported mechanism (ENV_FILE).

    We explicitly point ENV_FILE at finance_app/.env so the DB credentials used
    by tests always match the project's primary configuration.
    """

    finance_app_dir = Path(__file__).resolve().parents[1]
    env_path = finance_app_dir / ".env"
    if not env_path.exists():
        raise RuntimeError(f"Expected dotenv at {env_path}, but it does not exist")

    os.environ.setdefault("APP_ENV", "test")
    os.environ["ENV_FILE"] = str(env_path)

    # Clear caches so settings/engine pick up ENV_FILE reliably.
    from finance_app.config import get_settings
    from finance_app.app.database import get_engine, get_sessionmaker

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set (check finance_app/.env)")


@pytest.fixture(scope="session")
def app():
    from finance_app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def engine() -> Engine:
    from finance_app.config import get_settings

    settings = get_settings()
    # Build an engine explicitly for tests so we can enforce a connect timeout
    # while still using the primary DATABASE_URL from finance_app/.env.
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    # Fail fast with a clear error if DB is unreachable.
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Cannot connect to the primary DATABASE_URL from finance_app/.env. "
            "Fix credentials/connectivity before running tests."
        ) from exc
    return engine


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """A SQLAlchemy Session wrapped in an outer transaction.

    Each test runs inside a transaction that is rolled back at teardown, so the
    tests can safely use the *primary* DB without leaving data behind.

    This uses a nested transaction (SAVEPOINT) pattern so code under test can
    call session.commit() freely.
    """

    connection = engine.connect()
    outer_tx = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans: Any) -> None:  # noqa: ANN401
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_tx.rollback()
        connection.close()


@pytest_asyncio.fixture()
async def client(app, db_session: Session):
    from finance_app.app.dependencies import get_db

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_user(db_session: Session):
    from finance_app.app.models.user import User, UserRole
    from finance_app.app.utils.hashing import hash_password

    def _make(*, email: str, password: str = "password123", role: str = "viewer", full_name: str | None = None) -> User:
        user = User(email=email, hashed_password=hash_password(password), full_name=full_name, role=UserRole(role))
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture()
def make_category(db_session: Session):
    from finance_app.app.models.category import Category
    from finance_app.app.models.enums import TransactionType

    def _make(*, name: str, tx_type: str) -> Category:
        cat = Category(name=name, type=TransactionType(tx_type))
        db_session.add(cat)
        db_session.commit()
        db_session.refresh(cat)
        return cat

    return _make


@pytest_asyncio.fixture()
async def tokens(client: httpx.AsyncClient, make_user):
    """Create 3 users (viewer/analyst/admin) and return their bearer tokens."""

    # Create users directly so we can control roles deterministically.
    from uuid import uuid4

    viewer = make_user(email=f"viewer-{uuid4()}@example.com", role="viewer")
    analyst = make_user(email=f"analyst-{uuid4()}@example.com", role="analyst")
    admin = make_user(email=f"admin-{uuid4()}@example.com", role="admin")

    async def _login(email: str) -> str:
        r = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str) and body["access_token"]
        return body["access_token"]

    return {
        "viewer": {"user": viewer, "token": await _login(viewer.email)},
        "analyst": {"user": analyst, "token": await _login(analyst.email)},
        "admin": {"user": admin, "token": await _login(admin.email)},
    }


@pytest.fixture()
def sample_categories(make_category):
    income = make_category(name="Salary", tx_type="income")
    expense = make_category(name="Groceries", tx_type="expense")
    return {"income": income, "expense": expense}


@pytest.fixture()
def make_transaction(db_session: Session):
    from finance_app.app.models.transaction import Transaction
    from finance_app.app.models.enums import TransactionType

    def _make(*, user_id: UUID, category_id: UUID, tx_type: str, amount: Decimal, tx_date: date, notes: str | None = None) -> Transaction:
        tx = Transaction(
            user_id=user_id,
            category_id=category_id,
            type=TransactionType(tx_type),
            amount=amount,
            date=tx_date,
            notes=notes,
        )
        db_session.add(tx)
        db_session.commit()
        db_session.refresh(tx)
        return tx

    return _make


@pytest.fixture()
def auth_header():
    return _auth_header
