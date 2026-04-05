import argparse
import os
import secrets
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finance_app.app.database import get_sessionmaker
from finance_app.app.models.category import Category
from finance_app.app.models.enums import TransactionType
from finance_app.app.models.transaction import Transaction
from finance_app.app.models.user import User, UserRole
from finance_app.app.utils.hashing import hash_password


def _get_or_create_category(db: Session, name: str, cat_type: TransactionType) -> Category:
	"""Return an existing category or create it within the current transaction."""
	category = db.scalar(select(Category).where(Category.name == name, Category.type == cat_type))
	if category:
		return category
	category = Category(name=name, type=cat_type)
	db.add(category)
	db.flush()
	return category


def _get_or_create_user(db: Session, email: str, role: UserRole, full_name: str, default_password: str) -> User:
	"""Return an existing user or create one with the provided seed attributes."""
	user = db.scalar(select(User).where(User.email == email))
	if user:
		if user.role != role:
			user.role = role
		if user.full_name != full_name:
			user.full_name = full_name
		return user

	user = User(
		email=email,
		hashed_password=hash_password(default_password),
		full_name=full_name,
		role=role,
	)
	db.add(user)
	db.flush()
	return user


def _seed_transactions(db: Session, users: dict[str, User], categories: dict[str, Category]) -> int:
	"""Insert sample transactions once and report how many rows were added.

	This seeder is idempotent for transactions: if any transaction row already
	exists, no inserts occur and the function returns `0`.

	Args:
		db (Session): Active database session.
		users (dict[str, User]): Seeded users keyed by logical role label.
		categories (dict[str, Category]): Seeded categories keyed by name.

	Returns:
		int: Number of inserted transactions, or `0` when existing data is detected.

	Raises:
		None.
	"""
	existing = db.scalar(select(Transaction.id).limit(1))
	if existing:
		return 0

	rows = [
		# Admin sample data
		Transaction(user_id=users["admin"].id, amount=Decimal("85000.00"), type=TransactionType.income, category_id=categories["Salary"].id, date=date(2026, 1, 2), notes="Annual salary"),
		Transaction(user_id=users["admin"].id, amount=Decimal("32000.50"), type=TransactionType.expense, category_id=categories["Rent"].id, date=date(2026, 1, 5), notes="Rent payments"),
		Transaction(user_id=users["admin"].id, amount=Decimal("10300.00"), type=TransactionType.expense, category_id=categories["Food"].id, date=date(2026, 2, 14), notes="Groceries and dining"),
		# Analyst sample data
		Transaction(user_id=users["analyst"].id, amount=Decimal("6500.00"), type=TransactionType.income, category_id=categories["Freelance"].id, date=date(2026, 3, 8), notes="Client project"),
		Transaction(user_id=users["analyst"].id, amount=Decimal("1800.00"), type=TransactionType.expense, category_id=categories["Utilities"].id, date=date(2026, 3, 10), notes="Monthly bills"),
		# Viewer sample data
		Transaction(user_id=users["viewer"].id, amount=Decimal("2000.00"), type=TransactionType.income, category_id=categories["Salary"].id, date=date(2026, 4, 1), notes="Part-time salary"),
		Transaction(user_id=users["viewer"].id, amount=Decimal("550.00"), type=TransactionType.expense, category_id=categories["Food"].id, date=date(2026, 4, 2), notes="Weekly spend"),
	]
	db.add_all(rows)
	return len(rows)



def _parse_args() -> argparse.Namespace:
	"""Parse CLI arguments for the seeding command."""
	parser = argparse.ArgumentParser(description="Seed Finance Tracker database with sample data")
	parser.add_argument(
		"--password",
		help="Default password for seeded users (overrides SEED_DEFAULT_PASSWORD)",
		default=None,
	)
	parser.add_argument(
		"--show-password",
		help="Print the seeded password to stdout (useful for local dev only)",
		action="store_true",
	)
	return parser.parse_args()


def _resolve_seed_password(password_override: str | None) -> str:
	"""Resolve seed password using override, environment, then random fallback.

	Password selection priority is: explicit CLI override first, then
	`SEED_DEFAULT_PASSWORD` from environment, then a generated secure random
	password.

	Args:
		password_override (str | None): Password provided via CLI option.

	Returns:
		str: Password used for newly created seeded users.

	Raises:
		None.
	"""
	if password_override:
		return password_override
	env_password = os.getenv("SEED_DEFAULT_PASSWORD")
	if env_password:
		return env_password
	# Secure-by-default: generate a random password for seeded users.
	return secrets.token_urlsafe(18)


def main() -> None:
	"""Run the database seeding workflow for categories, users, and transactions."""
	args = _parse_args()
	default_password = _resolve_seed_password(args.password)

	SessionLocal = get_sessionmaker()
	db = SessionLocal()
	try:
		categories = {
			"Food": _get_or_create_category(db, "Food", TransactionType.expense),
			"Rent": _get_or_create_category(db, "Rent", TransactionType.expense),
			"Utilities": _get_or_create_category(db, "Utilities", TransactionType.expense),
			"Salary": _get_or_create_category(db, "Salary", TransactionType.income),
			"Freelance": _get_or_create_category(db, "Freelance", TransactionType.income),
		}

		users = {
			"viewer": _get_or_create_user(db, "viewer@example.com", UserRole.viewer, "Viewer User", default_password),
			"analyst": _get_or_create_user(db, "analyst@example.com", UserRole.analyst, "Analyst User", default_password),
			"admin": _get_or_create_user(db, "admin@example.com", UserRole.admin, "Admin User", default_password),
		}

		seeded_transactions = _seed_transactions(db, users, categories)
		db.commit()

		print("Seed completed")
		print(f"Users: {', '.join(users.keys())}")
		print(f"Categories: {', '.join(categories.keys())}")
		print(f"Transactions added: {seeded_transactions}")
		if args.show_password:
			print(f"Default password for seeded users: {default_password}")
	except SQLAlchemyError:
		db.rollback()
		raise
	finally:
		db.close()


if __name__ == "__main__":
	main()

