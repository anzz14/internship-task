from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finance_app.app.models.enums import TransactionType
from finance_app.app.utils.sentinel import UNSET


class CategoryCreateRequest(BaseModel):
    """Request model for creating a category."""
    name: str = Field(min_length=1, max_length=120)
    type: TransactionType

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Normalize category names by trimming surrounding whitespace."""
        return value.strip()


class CategoryUpdateRequest(BaseModel):
    """Request model for partially updating a category."""
    name: Any = Field(default_factory=lambda: UNSET)
    type: TransactionType | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> Any:
        """Normalize update name input while preserving UNSET semantics."""
        if value is UNSET:
            return UNSET
        if value is None:
            return None
        normalized = str(value).strip()
        if normalized and len(normalized) > 120:
            raise ValueError("name must be at most 120 characters")
        return normalized or None


class CategoryResponse(BaseModel):
    """Response model for category resources."""
    id: UUID
    name: str
    type: TransactionType

    model_config = ConfigDict(from_attributes=True)
