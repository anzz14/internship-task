from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from finance_app.config import get_settings


class InvalidTokenError(ValueError):
	"""Raised when access token decoding or validation fails."""
	pass


class AccessTokenPayload(BaseModel):
	"""Typed representation of access token claims used by the API."""
	sub: str
	exp: datetime | int


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
	"""Create and sign a JWT access token.

	The token always includes `sub` and `exp` claims. Token lifetime defaults to
	configured settings and can be overridden per call with `expires_minutes`.

	Args:
		subject (str): Subject claim value, typically a user id.
		expires_minutes (int | None): Optional expiry override in minutes. When
			`None`, the configured default expiration is used.

	Returns:
		str: Encoded JWT token string.

	Raises:
		None.
	"""
	settings = get_settings()
	expire_delta = timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
	expire_at = datetime.now(timezone.utc) + expire_delta
	payload = {
		"sub": subject,
		"exp": expire_at,
	}
	return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> AccessTokenPayload:
	"""Decode and validate a JWT access token into a typed payload.

	This wraps JWT decoding and payload validation errors in `InvalidTokenError`
	to provide a single domain-specific failure type for authentication code.

	Args:
		token (str): Encoded JWT token string.

	Returns:
		AccessTokenPayload: Validated token payload containing at least `sub` and `exp`.

	Raises:
		InvalidTokenError: Raised when signature/claims verification fails or the
			decoded payload does not match the expected schema.
	"""
	settings = get_settings()
	try:
		data: dict[str, Any] = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
		return AccessTokenPayload.model_validate(data)
	except (JWTError, ValidationError) as exc:
		raise InvalidTokenError("Invalid token") from exc

