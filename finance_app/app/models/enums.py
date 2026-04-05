import enum


class TransactionType(str, enum.Enum):
	"""Enumerates supported transaction directions."""
	income = "income"
	expense = "expense"
