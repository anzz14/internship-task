from uuid import UUID

from fastapi import APIRouter, status

from finance_app.app.dependencies import AdminUserDep, DbDep
from finance_app.app.schemas.user import UserResponse, UserRoleUpdateRequest
from finance_app.app.services.user_service import (
	delete_user as svc_delete_user,
	get_user_or_404,
	list_users as svc_list_users,
	update_user_role as svc_update_user_role,
)


router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def get_users(
	db: DbDep,
	_admin: AdminUserDep,
) -> list[UserResponse]:
	"""List all users."""
	users = svc_list_users(db)
	return [UserResponse.model_validate(user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
	user_id: UUID,
	db: DbDep,
	_admin: AdminUserDep,
) -> UserResponse:
	"""Return a single user by id."""
	user = get_user_or_404(db, user_id)
	return UserResponse.model_validate(user)


@router.put("/{user_id}/role", response_model=UserResponse)
def update_role(
	user_id: UUID,
	payload: UserRoleUpdateRequest,
	db: DbDep,
	_admin: AdminUserDep,
) -> UserResponse:
	"""Update a user's role."""
	user = svc_update_user_role(db, user_id, payload.role)
	return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(
	user_id: UUID,
	db: DbDep,
	_admin: AdminUserDep,
) -> None:
	"""Delete a user by id."""
	svc_delete_user(db, user_id)

