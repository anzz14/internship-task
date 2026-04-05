from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finance_app.app.models.user import User, UserRole


def list_users(db: Session) -> list[User]:
	"""Return all users ordered by creation time descending."""
	return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


def get_user_or_404(db: Session, user_id: UUID) -> User:
	"""Return a user by id or raise 404 when missing."""
	user = db.scalar(select(User).where(User.id == user_id))
	if not user:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
	return user


def update_user_role(db: Session, user_id: UUID, role: UserRole) -> User:
	"""Update a user's role and persist the change."""
	user = get_user_or_404(db, user_id)
	user.role = role
	try:
		db.commit()
		db.refresh(user)
	except SQLAlchemyError:
		db.rollback()
		raise
	return user


def delete_user(db: Session, user_id: UUID) -> None:
	"""Delete a user by id and commit the change."""
	user = get_user_or_404(db, user_id)
	try:
		db.delete(user)
		db.commit()
	except SQLAlchemyError:
		db.rollback()
		raise
