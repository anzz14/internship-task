import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finance_app.app.database import Base


class UserRole(str, enum.Enum):
	"""Enumerates application authorization roles."""
	viewer = "viewer"
	analyst = "analyst"
	admin = "admin"


class User(Base):
	"""User model storing identity, credentials, and role membership."""
	__tablename__ = "users"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
	hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
	full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	role: Mapped[UserRole] = mapped_column(
		Enum(UserRole, name="user_role"),
		nullable=False,
		default=UserRole.viewer,
		server_default=UserRole.viewer.value,
	)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

	transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

