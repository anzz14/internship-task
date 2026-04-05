from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from finance_app.app.models.user import UserRole


class UserRegisterRequest(BaseModel):
	"""Request model for user registration."""
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)
	full_name: str | None = Field(default=None, max_length=255)

	@field_validator("email", mode="before")
	@classmethod
	def normalize_email(cls, value: str) -> str:
		"""Normalize email input by trimming and lowercasing."""
		return value.strip().lower()

	@field_validator("full_name", mode="before")
	@classmethod
	def normalize_full_name(cls, value: str | None) -> str | None:
		"""Trim full name input and map blanks to None."""
		if value is None:
			return None
		normalized = value.strip()
		return normalized or None


class UserLoginRequest(BaseModel):
	"""Request model for user login."""
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)

	@field_validator("email", mode="before")
	@classmethod
	def normalize_email(cls, value: str) -> str:
		"""Normalize login email input by trimming and lowercasing."""
		return value.strip().lower()


class UserResponse(BaseModel):
	"""Response model representing a user resource."""
	id: UUID
	email: EmailStr
	full_name: str | None
	role: UserRole
	created_at: datetime

	model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
	"""Response model containing bearer access token information."""
	access_token: str
	token_type: str = "bearer"


class UserRoleUpdateRequest(BaseModel):
	"""Request model for updating a user's role."""
	role: UserRole

