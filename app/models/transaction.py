import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finance_app.app.database import Base
from finance_app.app.models.enums import TransactionType


class Transaction(Base):
	"""Transaction model representing a single financial entry."""
	__tablename__ = "transactions"
	__table_args__ = (CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),)

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	amount: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)
	type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"), nullable=False)
	category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
	date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
	notes: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

	user = relationship("User", back_populates="transactions")
	category = relationship("Category", back_populates="transactions")

