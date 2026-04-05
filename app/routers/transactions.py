from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, status

from finance_app.app.dependencies import AdminUserDep, CurrentUserDep, DbDep
from finance_app.app.models.enums import TransactionType
from finance_app.app.schemas.transaction import (
	TransactionCreateRequest,
	TransactionListResponse,
	TransactionResponse,
	TransactionUpdateRequest,
)
from finance_app.app.services.transaction_service import (
	create_transaction,
	delete_transaction,
	get_transaction_or_404,
	list_transactions,
	update_transaction,
	validate_transaction_filters_for_role,
)
from finance_app.app.utils.pagination import get_total_pages


router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def get_transactions(
	db: DbDep,
	current_user: CurrentUserDep,
	tx_type: TransactionType | None = Query(default=None, alias="type"),
	category_id: UUID | None = None,
	date_from: date | None = None,
	date_to: date | None = None,
	page: int = Query(1, ge=1),
	page_size: int = Query(20, ge=1, le=100),
) -> TransactionListResponse:
	"""List transactions with optional filters and pagination."""
	validate_transaction_filters_for_role(
		current_user,
		tx_type=tx_type,
		category_id=category_id,
		date_from=date_from,
		date_to=date_to,
	)

	items, total, safe_page, safe_page_size = list_transactions(
		db,
		current_user,
		tx_type=tx_type,
		category_id=category_id,
		date_from=date_from,
		date_to=date_to,
		page=page,
		page_size=page_size,
	)

	return TransactionListResponse(
		items=[TransactionResponse.model_validate(item) for item in items],
		page=safe_page,
		page_size=safe_page_size,
		total=total,
		total_pages=get_total_pages(total, safe_page_size),
	)


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_new_transaction(
	payload: TransactionCreateRequest,
	db: DbDep,
	current_user: CurrentUserDep,
) -> TransactionResponse:
	"""Create a new transaction for the current user or delegated target."""
	tx = create_transaction(db, payload, current_user)
	return TransactionResponse.model_validate(tx)


@router.get("/{tx_id}", response_model=TransactionResponse)
def get_transaction(
	tx_id: UUID,
	db: DbDep,
	current_user: CurrentUserDep,
) -> TransactionResponse:
	"""Return a single transaction by id with access checks."""
	tx = get_transaction_or_404(db, tx_id, current_user)
	return TransactionResponse.model_validate(tx)


@router.put("/{tx_id}", response_model=TransactionResponse)
def update_existing_transaction(
	tx_id: UUID,
	payload: TransactionUpdateRequest,
	db: DbDep,
	current_user: CurrentUserDep,
) -> TransactionResponse:
	"""Update an existing transaction by id."""
	tx = get_transaction_or_404(db, tx_id, current_user)
	updated = update_transaction(db, tx, payload)
	return TransactionResponse.model_validate(updated)


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_transaction(
	tx_id: UUID,
	db: DbDep,
	current_user: AdminUserDep,
) -> None:
	"""Delete a transaction by id."""
	tx = get_transaction_or_404(db, tx_id, current_user)
	delete_transaction(db, tx)

