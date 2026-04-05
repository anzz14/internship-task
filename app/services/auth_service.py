from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.app.models.user import User
from finance_app.app.schemas.user import UserRegisterRequest
from finance_app.app.utils.hashing import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
	"""Return a user by email if present."""
	stmt = select(User).where(User.email == email)
	return db.scalar(stmt)


def register_user(db: Session, payload: UserRegisterRequest) -> User:
	"""Register a new user account with unique email enforcement.

	This function checks for an existing account by email before creating a new
	user, then commits and refreshes the persisted record.

	Args:
		db (Session): Active database session.
		payload (UserRegisterRequest): Registration payload with email, password,
			and optional profile fields.

	Returns:
		User: The newly created and refreshed user entity.

	Raises:
		HTTPException: Raised with 409 when the email is already registered.
		SQLAlchemyError: Propagated when commit fails after rollback.
	"""
	existing = get_user_by_email(db, payload.email)
	if existing:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	user = User(
		email=payload.email,
		hashed_password=hash_password(payload.password),
		full_name=payload.full_name,
	)
	db.add(user)
	try:
		db.commit()
	except SQLAlchemyError:
		db.rollback()
		raise
	db.refresh(user)
	return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
	"""Authenticate a user by email and password.

	Authentication has two failure paths that both return `None`: when no user
	exists for the provided email, and when password verification fails.

	Args:
		db (Session): Active database session.
		email (str): Candidate account email.
		password (str): Plaintext password to verify.

	Returns:
		User | None: The matching user when credentials are valid, otherwise
			`None`.

	Raises:
		SQLAlchemyError: Propagated if user lookup fails at the database layer.
	"""
	user = get_user_by_email(db, email)
	if not user:
		return None
	if not verify_password(password, user.hashed_password):
		return None
	return user

