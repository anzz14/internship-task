from collections.abc import Callable, Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.app.database import get_sessionmaker
from finance_app.app.models.user import User, UserRole
from finance_app.app.utils.jwt import InvalidTokenError, decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

TokenDep = Annotated[str, Depends(oauth2_scheme)]


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed after use."""
    # NOTE: Keep indentation spaces-only in this file to avoid
    # mixed-tab indentation issues under different editors.
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    token: TokenDep,
    db: DbDep,
) -> User:
    """Resolve the authenticated user from a bearer token.

    The function first decodes token claims and parses the subject as a UUID.
    It then loads the user from the database. Both invalid-token and missing-user
    scenarios are treated as unauthorized.

    Args:
        token (TokenDep): OAuth2 bearer token string from the request.
        db (DbDep): Active database dependency/session.

    Returns:
        User: The authenticated user entity.

    Raises:
        HTTPException: Raised with 401 when token decoding/parsing fails.
        HTTPException: Raised with 401 when the token is valid but the user no longer exists.
    """
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload.sub)
    except (InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from exc

    stmt = select(User).where(User.id == user_id)
    user = db.scalar(stmt)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_role(
    *roles: UserRole,
    forbidden_detail: str | None = None,
) -> Callable[[CurrentUserDep], User]:
    """Create a role-checking dependency function.

    This function is a factory: it returns a dependency callable that FastAPI can
    use in `Depends(...)`, rather than acting as a dependency itself.

    Args:
        *roles (UserRole): Roles that are allowed to access the endpoint.
        forbidden_detail (str | None): Optional custom 403 message when role check fails.

    Returns:
        Callable[[CurrentUserDep], User]: A dependency callable that validates the
            current user's role and returns that user on success.

    Raises:
        HTTPException: Raised with 403 by the returned checker when role is not allowed.
    """

    allowed = set(roles)

    def _checker(current_user: CurrentUserDep) -> User:
        if current_user.role not in allowed:
            allowed_labels = ", ".join(sorted(role.value for role in allowed))
            detail = forbidden_detail or f"Required role: {allowed_labels}"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        return current_user

    return _checker


def require_analyst_or_admin(current_user: CurrentUserDep) -> User:
    """Enforce analyst-or-admin access for analytics endpoints."""
    return require_role(
        UserRole.analyst,
        UserRole.admin,
        forbidden_detail="Viewer cannot view analytics",
    )(current_user)


AnalystOrAdminUserDep = Annotated[User, Depends(require_analyst_or_admin)]
AdminUserDep = Annotated[
    User,
    Depends(require_role(UserRole.admin, forbidden_detail="Admin access required")),
]

