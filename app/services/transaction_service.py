from typing import Any
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.selectable import Select
from sqlalchemy.orm import Session

from finance_app.app.models.category import Category
from finance_app.app.models.enums import TransactionType
from finance_app.app.models.transaction import Transaction
from finance_app.app.models.user import User, UserRole
from finance_app.app.schemas.transaction import TransactionCreateRequest, TransactionUpdateRequest
from finance_app.app.utils.pagination import get_pagination
from finance_app.app.utils.sentinel import UNSET


def _base_scope(stmt: Select[Any], current_user: User) -> Select[Any]:
	"""Scope transaction query by actor role."""
	if current_user.role == UserRole.admin:
		return stmt
	return stmt.where(Transaction.user_id == current_user.id)


def validate_transaction_filters_for_role(
	current_user: User,
	*,
	tx_type: TransactionType | None,
	category_id: UUID | None,
	date_from: date | None,
	date_to: date | None,
) -> None:
	"""Validate role permissions for transaction filter usage.

	Viewers are allowed to list their transactions but are not allowed to apply
	advanced filters. Analysts and admins are allowed to apply all provided
	filters.

	Args:
		current_user (User): Authenticated user requesting the transaction list.
		tx_type (TransactionType | None): Optional transaction type filter.
		category_id (UUID | None): Optional category filter.
		date_from (date | None): Optional inclusive start date filter.
		date_to (date | None): Optional inclusive end date filter.

	Returns:
		None: Returns normally when the filter combination is allowed.

	Raises:
		HTTPException: Raised with 403 when a viewer applies any advanced filter.
	"""
	if current_user.role == UserRole.viewer and any((tx_type, category_id, date_from, date_to)):
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Viewer cannot apply filters to transactions",
		)


def list_transactions(
	db: Session,
	current_user: User,
	*,
	tx_type: TransactionType | None,
	category_id: UUID | None,
	date_from: date | None,
	date_to: date | None,
	page: int,
	page_size: int,
) -> tuple[list[Transaction], int, int, int]:
	"""List transactions with role-aware scoping, filters, and pagination.

	For admins, results include all users' transactions. For non-admin users,
	results are scoped to the caller's own transactions. Optional filters are
	then applied, followed by descending date/creation ordering and pagination.

	Args:
		db (Session): Active database session.
		current_user (User): Authenticated user requesting the list.
		tx_type (TransactionType | None): Optional transaction type filter.
		category_id (UUID | None): Optional category filter.
		date_from (date | None): Optional inclusive start date filter.
		date_to (date | None): Optional inclusive end date filter.
		page (int): Requested 1-based page number.
		page_size (int): Requested page size before safety bounds are applied.

	Returns:
		tuple[list[Transaction], int, int, int]: A 4-tuple containing
			(items, total, page, page_size), where items is the current page of
			transactions, total is the full filtered count, page is the normalized
			page number, and page_size is the normalized page size.

	Raises:
		SQLAlchemyError: Propagated if database query execution fails.
	"""
	stmt = _base_scope(select(Transaction), current_user)

	if tx_type:
		stmt = stmt.where(Transaction.type == tx_type)
	if category_id:
		stmt = stmt.where(Transaction.category_id == category_id)
	if date_from:
		stmt = stmt.where(Transaction.date >= date_from)
	if date_to:
		stmt = stmt.where(Transaction.date <= date_to)

	count_stmt = select(func.count()).select_from(stmt.subquery())
	total = db.scalar(count_stmt) or 0

	safe_page_size, offset = get_pagination(page, page_size)
	stmt = stmt.order_by(Transaction.date.desc(), Transaction.created_at.desc()).offset(offset).limit(safe_page_size)
	items = list(db.scalars(stmt).all())
	return items, total, max(page, 1), safe_page_size


def get_transaction_or_404(db: Session, tx_id: UUID, current_user: User) -> Transaction:
	"""Return a transaction by id, enforcing role-based access checks.

	Admins may access any transaction. Non-admin users can only access
	transactions they own.

	Args:
		db (Session): Active database session.
		tx_id (UUID): Transaction identifier to load.
		current_user (User): Authenticated user requesting access.

	Returns:
		Transaction: The matching transaction when found and authorized.

	Raises:
		HTTPException: Raised with 404 when the transaction does not exist.
		HTTPException: Raised with 403 when a non-admin accesses another user's transaction.
	"""
	tx = db.scalar(select(Transaction).where(Transaction.id == tx_id))
	if not tx:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
	if current_user.role != UserRole.admin and tx.user_id != current_user.id:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="You are not allowed to access this transaction",
		)
	return tx


def _validate_category_type(db: Session, category_id: UUID, tx_type: TransactionType) -> None:
	"""Validate category existence and type compatibility."""
	category = db.scalar(select(Category).where(Category.id == category_id))
	if not category:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
	if category.type != tx_type:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Category type mismatch")


def create_transaction(db: Session, payload: TransactionCreateRequest, actor: User) -> Transaction:
	"""Create a transaction for the actor or an admin-delegated target user.

	When `target_user_id` is omitted, the transaction is created for the acting
	user. When `target_user_id` is provided, only admins may delegate creation,
	and the target user must exist.

	Args:
		db (Session): Active database session.
		payload (TransactionCreateRequest): Transaction creation payload.
		actor (User): Authenticated user performing the action.

	Returns:
		Transaction: The committed and refreshed transaction record.

	Raises:
		HTTPException: Raised with 403 when a non-admin sets `target_user_id`.
		HTTPException: Raised with 404 when `target_user_id` references no user.
		HTTPException: Raised with 404 or 422 if category validation fails.
		SQLAlchemyError: Propagated when commit fails after rollback.
	"""
	owner_id = actor.id
	if payload.target_user_id is not None:
		if actor.role != UserRole.admin:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Only admin can create transactions for another user",
			)
		target_user = db.scalar(select(User).where(User.id == payload.target_user_id))
		if not target_user:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
		owner_id = payload.target_user_id
	_validate_category_type(db, payload.category_id, payload.type)

	tx = Transaction(
		user_id=owner_id,
		amount=payload.amount,
		type=payload.type,
		category_id=payload.category_id,
		date=payload.date,
		notes=payload.notes,
	)
	db.add(tx)
	try:
		db.commit()
		db.refresh(tx)
	except SQLAlchemyError:
		db.rollback()
		raise
	return tx


def update_transaction(db: Session, tx: Transaction, payload: TransactionUpdateRequest) -> Transaction:
	"""Apply a partial transaction update and persist the result.

	Most fields use `None` to mean "leave unchanged" in this update flow.
	`notes` is handled differently: it uses the `UNSET` sentinel so callers can
	distinguish "omit notes field" (no change) from "set notes to null".

	Args:
		db (Session): Active database session.
		tx (Transaction): Existing transaction entity to update.
		payload (TransactionUpdateRequest): Partial update payload.

	Returns:
		Transaction: The committed and refreshed transaction record.

	Raises:
		HTTPException: Raised with 404 or 422 if category/type validation fails.
		SQLAlchemyError: Propagated when commit fails after rollback.
	"""
	final_type = payload.type if payload.type is not None else tx.type
	final_category_id = payload.category_id if payload.category_id is not None else tx.category_id
	_validate_category_type(db, final_category_id, final_type)

	tx.type = final_type
	tx.category_id = final_category_id
	if payload.amount is not None:
		tx.amount = payload.amount
	if payload.date is not None:
		tx.date = payload.date
	if payload.notes is not UNSET:
		tx.notes = payload.notes

	try:
		db.commit()
		db.refresh(tx)
	except SQLAlchemyError:
		db.rollback()
		raise
	return tx


def delete_transaction(db: Session, tx: Transaction) -> None:
	"""Delete a transaction and commit the deletion.

	Args:
		db (Session): Active database session.
		tx (Transaction): Transaction entity to delete.

	Returns:
		None: The transaction is removed when commit succeeds.

	Raises:
		SQLAlchemyError: Propagated when delete or commit fails after rollback.
	"""
	try:
		db.delete(tx)
		db.commit()
	except SQLAlchemyError:
		db.rollback()
		raise

