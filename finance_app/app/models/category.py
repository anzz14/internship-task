import uuid

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finance_app.app.database import Base
from finance_app.app.models.enums import TransactionType


class Category(Base):
	"""Category model used to classify income and expense transactions."""
	__tablename__ = "categories"
	__table_args__ = (UniqueConstraint("name", "type", name="uq_categories_name_type"),)

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	name: Mapped[str] = mapped_column(String(120), nullable=False)
	type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"), nullable=False)

	transactions = relationship("Transaction", back_populates="category")

