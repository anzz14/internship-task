from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from finance_app.config import get_settings


Base = declarative_base()

# Ensure all models are registered before mapper configuration occurs.
from finance_app.app.models import category, transaction, user  # noqa: F401,E402


@lru_cache
def get_engine() -> Engine:
	"""Create and cache the SQLAlchemy engine using application settings."""
	settings = get_settings()
	return create_engine(
		settings.database_url,
		pool_pre_ping=True,
		pool_size=settings.pool_size,
		max_overflow=settings.max_overflow,
	)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
	"""Create and cache the SQLAlchemy session factory bound to the engine."""
	return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

