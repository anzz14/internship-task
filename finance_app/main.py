import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from finance_app.app.database import get_sessionmaker
from finance_app.app.routers.analytics import router as analytics_router
from finance_app.app.routers.auth import router as auth_router
from finance_app.app.routers.categories import router as categories_router
from finance_app.app.routers.transactions import router as transactions_router
from finance_app.app.routers.users import router as users_router


app = FastAPI(title="Finance Tracker API")
logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a standardized response for request validation errors."""
    logger.warning("Request validation failed", extra={"errors": exc.errors()})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(OperationalError)
async def operational_error_handler(_request: Request, _exc: OperationalError) -> JSONResponse:
    """Return a service-unavailable response for operational database errors."""
    logger.warning("Operational database error", exc_info=_exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database unavailable. Check DATABASE_URL credentials and connectivity.",
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
    """Return a generic database error response for uncaught SQLAlchemy errors."""
    logger.exception("Unhandled SQLAlchemy error", exc_info=_exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error while processing request."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Return a generic internal-error response for uncaught exceptions."""
    logger.exception("Unhandled application exception", exc_info=_exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )

app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(analytics_router)
app.include_router(users_router)


@app.get("/")
def root() -> dict[str, object]:
    """Return a small index of the most useful API routes."""
    return {
        "message": "API running",
        "docs": "/docs",
        "routes": {
            "auth": {
                "register": "/api/auth/register",
                "login": "/api/auth/login",
                "refresh": "/api/auth/refresh",
            },
            "health": {
                "status": "/health",
                "database": "/health/db",
            },
            "resources": {
                "users": "/api/users",
                "categories": "/api/categories",
                "transactions": "/api/transactions",
                "analytics": "/api/analytics/summary",
            },
        },
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return process-level health status."""
    return {"status": "ok"}


@app.get("/health/db")
def health_check_db() -> dict[str, str]:
    """Return database connectivity health status."""
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except OperationalError:
        logger.warning("Health DB check failed: database unavailable", exc_info=True)
        return {"status": "unavailable"}
    except SQLAlchemyError:
        logger.exception("Health DB check failed with SQLAlchemy error", exc_info=True)
        return {"status": "error"}
    finally:
        db.close()

