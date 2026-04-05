from fastapi import APIRouter, Query

from finance_app.app.dependencies import AnalystOrAdminUserDep, DbDep
from finance_app.app.schemas.analytics import CategoryBreakdownItem, MonthlyTotalsItem, RecentTransactionItem, SummaryResponse
from finance_app.app.services.analytics_service import get_by_category, get_monthly, get_recent, get_summary


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=SummaryResponse)
def summary(
	db: DbDep,
	current_user: AnalystOrAdminUserDep,
) -> SummaryResponse:
	"""Return summary analytics for the authorized user scope."""
	return get_summary(db, current_user)


@router.get("/by-category", response_model=list[CategoryBreakdownItem])
def by_category(
	db: DbDep,
	current_user: AnalystOrAdminUserDep,
) -> list[CategoryBreakdownItem]:
	"""Return category breakdown analytics for the authorized user scope."""
	return get_by_category(db, current_user)


@router.get("/monthly", response_model=list[MonthlyTotalsItem])
def monthly(
	db: DbDep,
	current_user: AnalystOrAdminUserDep,
) -> list[MonthlyTotalsItem]:
	"""Return monthly aggregate analytics for the authorized user scope."""
	return get_monthly(db, current_user)


@router.get("/recent", response_model=list[RecentTransactionItem])
def recent(
	db: DbDep,
	current_user: AnalystOrAdminUserDep,
	limit: int = Query(default=5, ge=1, le=100),
) -> list[RecentTransactionItem]:
	"""Return recent transactions for the authorized user scope."""
	return get_recent(db, current_user, limit)

