# app/repos/order_repo.py
from sqlalchemy.orm import Session
from app.data.models.order import OrderModel


class OrderRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_order(self, order: OrderModel) -> OrderModel:
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def get_order(self, order_id: int) -> OrderModel | None:
        return self.db.get(OrderModel, order_id)

    def update_order_status(self, order_id: int, status: str) -> OrderModel | None:
        order = self.get_order(order_id)
        if order:
            order.status = status
            self.db.commit()
            self.db.refresh(order)
        return order