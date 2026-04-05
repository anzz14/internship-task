import os
from passlib.context import CryptContext


if os.environ.get("APP_ENV") == "test":
	pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)
else:
	pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
	"""Hash a plaintext password using the configured password context."""
	return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
	"""Verify a plaintext password against its hashed representation."""
	return pwd_context.verify(plain_password, hashed_password)

