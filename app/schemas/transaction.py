from datetime import date as dt_date
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finance_app.app.models.enums import TransactionType
from finance_app.app.utils.sentinel import UNSET


class TransactionCreateRequest(BaseModel):
	"""Request model for creating a transaction."""
	amount: Decimal = Field(gt=0)
	type: TransactionType
	category_id: UUID
	date: dt_date
	notes: str | None = None
	target_user_id: UUID | None = None

	@field_validator("notes", mode="before")
	@classmethod
	def normalize_notes(cls, value: str | None) -> str | None:
		"""Trim optional notes and convert blank input to None."""
		if value is None:
			return None
		normalized = value.strip()
		return normalized or None


class TransactionUpdateRequest(BaseModel):
	"""Request model for partially updating a transaction."""
	amount: Decimal | None = Field(default=None, gt=0)
	type: TransactionType | None = None
	category_id: UUID | None = None
	date: dt_date | None = None
	notes: Any = Field(default_factory=lambda: UNSET)

	@field_validator("notes", mode="before")
	@classmethod
	def normalize_notes(cls, value: Any) -> Any:
		"""Normalize optional notes while preserving UNSET behavior."""
		if value is UNSET:
			return UNSET
		if value is None:
			return None
		normalized = value.strip()
		return normalized or None


class TransactionResponse(BaseModel):
	"""Response model representing a transaction resource."""
	id: UUID
	user_id: UUID
	amount: Decimal
	type: TransactionType
	category_id: UUID
	date: dt_date
	notes: str | None
	created_at: datetime

	model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
	"""Paginated response model for transaction listings."""
	items: list[TransactionResponse]
	page: int
	page_size: int
	total: int
	total_pages: int

