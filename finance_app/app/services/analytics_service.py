from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import Session

from finance_app.app.models.category import Category
from finance_app.app.models.enums import TransactionType
from finance_app.app.models.transaction import Transaction
from finance_app.app.models.user import User, UserRole
from finance_app.app.schemas.analytics import CategoryBreakdownItem, MonthlyTotalsItem, RecentTransactionItem, SummaryResponse


def _scope_filter(current_user: User) -> ColumnElement[bool] | None:
	"""Return role-based transaction scope for analytics queries.

	Admins receive `None` to indicate no row-level filter should be applied.
	Non-admin users receive a `WHERE` predicate restricting rows to their own
	transactions.

	Args:
		current_user (User): Authenticated user requesting analytics data.

	Returns:
		ColumnElement[bool] | None: `None` for admin users, otherwise a SQLAlchemy
			boolean expression suitable for `WHERE`.

	Raises:
		None.
	"""
	if current_user.role == UserRole.admin:
		return None
	return Transaction.user_id == current_user.id


def get_summary(db: Session, current_user: User) -> SummaryResponse:
	"""Return income, expense, and balance totals for the visible scope."""
	income_sum = func.coalesce(
		func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)),
		0,
	)
	expense_sum = func.coalesce(
		func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)),
		0,
	)

	stmt = select(income_sum.label("total_income"), expense_sum.label("total_expenses"))
	scope = _scope_filter(current_user)
	if scope is not None:
		stmt = stmt.where(scope)

	row = db.execute(stmt).one()
	total_income = Decimal(row.total_income or 0)
	total_expenses = Decimal(row.total_expenses or 0)
	return SummaryResponse(
		total_income=total_income,
		total_expenses=total_expenses,
		balance=total_income - total_expenses,
	)


def get_by_category(db: Session, current_user: User) -> list[CategoryBreakdownItem]:
	"""Return category totals with role-dependent transaction join rules.

	The query always starts from categories so categories without transactions are
	still included. For admins, the outer join aggregates transactions from all
	users. For non-admin users, the join condition includes a user predicate so
	only that user's transactions contribute to totals.

	Args:
		db (Session): Active database session.
		current_user (User): Authenticated user requesting category breakdown.

	Returns:
		list[CategoryBreakdownItem]: Categories with aggregated amounts, ordered by
			total amount descending.

	Raises:
		SQLAlchemyError: Propagated if database query execution fails.
	"""
	join_condition = Category.id == Transaction.category_id
	if current_user.role != UserRole.admin:
		join_condition = and_(join_condition, Transaction.user_id == current_user.id)

	stmt = (
		select(
			Category.id.label("category_id"),
			Category.name.label("category_name"),
			Category.type.label("type"),
			func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
		)
		.select_from(Category)
		.outerjoin(Transaction, join_condition)
		.group_by(Category.id, Category.name, Category.type)
		.order_by(func.coalesce(func.sum(Transaction.amount), 0).desc())
	)

	rows = db.execute(stmt).all()
	return [
		CategoryBreakdownItem(
			category_id=row.category_id,
			category_name=row.category_name,
			type=row.type,
			total_amount=Decimal(row.total_amount),
		)
		for row in rows
	]


def get_monthly(db: Session, current_user: User) -> list[MonthlyTotalsItem]:
	"""Return month-level income, expense, and balance totals.

	Results are grouped by month and ordered chronologically ascending by month.
	Each returned item contains a `YYYY-MM` month label plus total income,
	total expenses, and computed balance for that month.

	Args:
		db (Session): Active database session.
		current_user (User): Authenticated user requesting monthly totals.

	Returns:
		list[MonthlyTotalsItem]: Chronologically ordered monthly aggregates.

	Raises:
		SQLAlchemyError: Propagated if database query execution fails.
	"""
	month_expr = func.date_trunc("month", Transaction.date)
	income_sum = func.coalesce(
		func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)),
		0,
	)
	expense_sum = func.coalesce(
		func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)),
		0,
	)

	stmt = select(month_expr.label("month"), income_sum.label("income"), expense_sum.label("expenses")).group_by(month_expr).order_by(month_expr)
	scope = _scope_filter(current_user)
	if scope is not None:
		stmt = stmt.where(scope)

	rows = db.execute(stmt).all()
	results: list[MonthlyTotalsItem] = []
	for row in rows:
		income = Decimal(row.income)
		expenses = Decimal(row.expenses)
		results.append(
			MonthlyTotalsItem(
				month=row.month.strftime("%Y-%m"),
				total_income=income,
				total_expenses=expenses,
				balance=income - expenses,
			)
		)
	return results


def get_recent(db: Session, current_user: User, limit: int) -> list[RecentTransactionItem]:
	"""Return the most recent visible transactions up to the provided limit."""
	stmt = select(Transaction).order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(limit)
	scope = _scope_filter(current_user)
	if scope is not None:
		stmt = stmt.where(scope)

	items = db.scalars(stmt).all()
	return [
		RecentTransactionItem(
			id=tx.id,
			amount=tx.amount,
			type=tx.type,
			category_id=tx.category_id,
			date=tx.date,
			notes=tx.notes,
		)
		for tx in items
	]

