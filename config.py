import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	"""Application settings loaded from environment variables."""
	# Prefer a single URL, but allow DB_* component vars too (common in docker).
	database_url: str | None = Field(
		default=None,
		validation_alias=AliasChoices("DATABASE_URL", "DB_URL", "SQLALCHEMY_DATABASE_URL"),
	)

	db_user: str | None = Field(default=None, validation_alias=AliasChoices("DB_USER", "POSTGRES_USER"))
	db_password: str | None = Field(default=None, validation_alias=AliasChoices("DB_PASSWORD", "POSTGRES_PASSWORD"))
	db_host: str = Field(default="localhost", validation_alias=AliasChoices("DB_HOST", "POSTGRES_HOST"))
	db_port: int = Field(default=5432, validation_alias=AliasChoices("DB_PORT", "POSTGRES_PORT"))
	db_name: str | None = Field(default=None, validation_alias=AliasChoices("DB_NAME", "POSTGRES_DB", "POSTGRES_DATABASE"))

	secret_key: str = Field(validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY", "JWT_SECRET"))
	access_token_expire_minutes: int = 60
	algorithm: str = "HS256"
	pool_size: int = 5
	max_overflow: int = 10

	@field_validator("algorithm")
	@classmethod
	def validate_algorithm(cls, value: str) -> str:
		"""Normalize and validate the configured JWT signing algorithm."""
		allowed = {"HS256", "HS384", "HS512"}
		normalized = value.strip().upper()
		if normalized not in allowed:
			raise ValueError(
				f"Unsupported JWT algorithm '{value}'. Allowed values: {', '.join(sorted(allowed))}."
			)
		return normalized

	@field_validator("database_url")
	@classmethod
	def normalize_database_url(cls, value: str | None) -> str | None:
		"""Normalize PostgreSQL URLs to explicitly use the psycopg driver."""
		# SQLAlchemy defaults `postgresql://` to psycopg2. We normalize to psycopg v3
		# so that a simple DATABASE_URL keeps working without requiring a driver hint.
		if value is None:
			return None
		if value.startswith("postgresql://"):
			return value.replace("postgresql://", "postgresql+psycopg://", 1)
		return value

	@model_validator(mode="after")
	def build_database_url_if_missing(self) -> "Settings":
		"""Build `database_url` from DB_* settings when a direct URL is absent.

		Two configuration styles are accepted: either provide `DATABASE_URL` (or
		its aliases), or provide component variables (`DB_USER`, `DB_PASSWORD`, and
		`DB_NAME`, with optional host/port overrides). If neither style provides
		enough data, validation fails.

		Args:
			self (Settings): Settings instance under validation.

		Returns:
			Settings: The same settings object with `database_url` populated.

		Raises:
			ValueError: Raised when neither a direct URL nor required DB_* components
				are fully provided.
		"""
		if self.database_url:
			return self

		if not (self.db_user and self.db_password and self.db_name):
			raise ValueError(
				"Missing database configuration. Set DATABASE_URL (recommended) or "
				"set DB_USER, DB_PASSWORD, and DB_NAME (optionally DB_HOST/DB_PORT)."
			)

		url = f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
		self.database_url = url
		return self

	model_config = SettingsConfigDict(case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
	"""Load and cache application settings with environment-aware precedence.

	Settings resolution prefers explicit configuration while keeping local
	development convenient. If `ENV_FILE` is set, that file is loaded. Otherwise,
	in local-development environments, a repository `.env` file is loaded when
	present. If neither applies, values come directly from process environment
	variables.

	Args:
		None.

	Returns:
		Settings: Cached application settings instance.

	Raises:
		ValidationError: Propagated when required settings are missing or invalid.
	"""
	env_file = os.getenv("ENV_FILE")
	if env_file:
		return Settings(_env_file=env_file)

	app_env = (os.getenv("APP_ENV") or "development").strip().lower()
	if app_env in {"development", "dev", "local"}:
		default_env_file = Path(__file__).resolve().parent / ".env"
		if default_env_file.exists():
			return Settings(_env_file=str(default_env_file))

	return Settings()

