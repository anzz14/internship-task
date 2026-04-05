from datetime import date
from decimal import Decimal
import enum
from uuid import UUID

from pydantic import BaseModel

from finance_app.app.models.enums import TransactionType


class ReportPeriod(str, enum.Enum):
	"""Enumerates supported analytics report periods."""
	all_time = "all-time"


class SummaryResponse(BaseModel):
	"""Response model for high-level income and expense totals."""
	total_income: Decimal
	total_expenses: Decimal
	balance: Decimal
	period: ReportPeriod = ReportPeriod.all_time


class CategoryBreakdownItem(BaseModel):
	"""Response item describing totals for a single category."""
	category_id: UUID
	category_name: str
	type: TransactionType
	total_amount: Decimal


class MonthlyTotalsItem(BaseModel):
	"""Response item describing totals for a single month."""
	month: str
	total_income: Decimal
	total_expenses: Decimal
	balance: Decimal


class RecentTransactionItem(BaseModel):
	"""Response item representing a recent transaction snapshot."""
	id: UUID
	amount: Decimal
	type: TransactionType
	category_id: UUID
	date: date
	notes: str | None

