from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, Numeric
from datetime import datetime, timezone

from app.data.database import Base

class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(String, nullable=False, default="PENDING")  # PENDING, PROCESSING, COMPLETED
    total = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))