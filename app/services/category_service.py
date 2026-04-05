from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance_app.app.models.category import Category
from finance_app.app.models.enums import TransactionType
from finance_app.app.schemas.category import CategoryCreateRequest, CategoryUpdateRequest
from finance_app.app.utils.sentinel import UNSET


def list_categories(db: Session, *, tx_type: TransactionType | None = None) -> list[Category]:
    """Return categories, optionally filtered by transaction type."""
    stmt = select(Category).order_by(Category.name.asc())
    if tx_type:
        stmt = stmt.where(Category.type == tx_type)
    return list(db.scalars(stmt).all())


def get_category_or_404(db: Session, category_id: UUID) -> Category:
    """Get category by id or raise 404."""
    category = db.scalar(select(Category).where(Category.id == category_id))
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def _ensure_name_available(
    db: Session,
    *,
    name: str,
    tx_type: TransactionType,
    exclude_id: UUID | None = None,
) -> None:
    """Ensure no conflicting category exists for a name/type pair.

    The optional `exclude_id` is used during updates so the current category
    record can be excluded from duplicate checks while validating a new name
    or type combination.

    Args:
        db (Session): Active database session.
        name (str): Candidate category name.
        tx_type (TransactionType): Candidate transaction type.
        exclude_id (UUID | None): Category id to exclude from conflict checks,
            typically the category being updated.

    Returns:
        None: Returns normally when no conflicting category exists.

    Raises:
        HTTPException: Raised with 409 when another category already uses the
            same name and transaction type.
    """
    stmt = select(Category).where(Category.name == name, Category.type == tx_type)
    if exclude_id:
        stmt = stmt.where(Category.id != exclude_id)
    existing = db.scalar(stmt)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with same name and type already exists",
        )


def create_category(db: Session, payload: CategoryCreateRequest) -> Category:
    """Create a category after duplicate-name checks."""
    name = payload.name
    _ensure_name_available(db, name=name, tx_type=payload.type)
    category = Category(name=name, type=payload.type)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: Category, payload: CategoryUpdateRequest) -> Category:
    """Update category name/type with duplicate-name checks."""
    if payload.name is UNSET:
        next_name = category.name
    elif payload.name is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Category name cannot be null")
    else:
        next_name = payload.name
    next_type = payload.type if payload.type is not None else category.type

    _ensure_name_available(db, name=next_name, tx_type=next_type, exclude_id=category.id)

    category.name = next_name
    category.type = next_type
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category: Category) -> None:
    """Delete a category, protecting categories referenced by transactions."""
    try:
        db.delete(category)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category cannot be deleted because it is used by transactions",
        )
