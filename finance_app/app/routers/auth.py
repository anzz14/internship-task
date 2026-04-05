from fastapi import APIRouter, HTTPException, status

from finance_app.app.dependencies import CurrentUserDep, DbDep
from finance_app.app.schemas.user import TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from finance_app.app.services.auth_service import authenticate_user, register_user
from finance_app.app.utils.jwt import create_access_token


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: DbDep) -> UserResponse:
	"""Register a new user account."""
	user = register_user(db, payload)
	return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: DbDep) -> TokenResponse:
	"""Authenticate a user and return a signed access token."""
	user = authenticate_user(db, payload.email, payload.password)
	if not user:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid authentication credentials",
		)

	token = create_access_token(subject=str(user.id))
	return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: CurrentUserDep) -> TokenResponse:
	"""Issue a fresh access token for the authenticated user."""
	token = create_access_token(subject=str(current_user.id))
	return TokenResponse(access_token=token)

