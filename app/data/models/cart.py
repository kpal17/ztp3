#app/data/models/cart.py
from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship

from app.data.database import Base


class CartModel(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    items = relationship(
        "CartItemModel",
        back_populates="cart",
        cascade="all, delete-orphan",
    )
