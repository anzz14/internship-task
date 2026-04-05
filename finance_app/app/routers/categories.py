from uuid import UUID

from fastapi import APIRouter, Query, status

from finance_app.app.dependencies import AdminUserDep, CurrentUserDep, DbDep
from finance_app.app.models.enums import TransactionType
from finance_app.app.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from finance_app.app.services.category_service import (
    create_category,
    delete_category,
    get_category_or_404,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def get_categories(
    db: DbDep,
    _current_user: CurrentUserDep,
    tx_type: TransactionType | None = Query(default=None, alias="type"),
) -> list[CategoryResponse]:
    """List categories with optional transaction type filtering."""
    items = list_categories(db, tx_type=tx_type)
    return [CategoryResponse.model_validate(item) for item in items]


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    db: DbDep,
    _current_user: CurrentUserDep,
) -> CategoryResponse:
    """Return a single category by id."""
    category = get_category_or_404(db, category_id)
    return CategoryResponse.model_validate(category)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_new_category(
    payload: CategoryCreateRequest,
    db: DbDep,
    _admin: AdminUserDep,
) -> CategoryResponse:
    """Create a new category."""
    created = create_category(db, payload)
    return CategoryResponse.model_validate(created)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_existing_category(
    category_id: UUID,
    payload: CategoryUpdateRequest,
    db: DbDep,
    _admin: AdminUserDep,
) -> CategoryResponse:
    """Update an existing category by id."""
    category = get_category_or_404(db, category_id)
    updated = update_category(db, category, payload)
    return CategoryResponse.model_validate(updated)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_category(
    category_id: UUID,
    db: DbDep,
    _admin: AdminUserDep,
) -> None:
    """Delete a category by id."""
    category = get_category_or_404(db, category_id)
    delete_category(db, category)
