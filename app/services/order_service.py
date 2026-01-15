# app/services/order_service.py
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.data.models.order import OrderModel
from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel
from app.repos.order_repo import OrderRepo
from app.services.notification_service import NotificationService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    """
    Serwis odpowiedzialny za domenę zamówień.
    Separacja od CartService zgodnie z wymaganiami.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = OrderRepo(db)
        self.notification_service = NotificationService()

    def create_order_from_cart(self, cart_id: int, user_id: int):
        """
        Use Case: Tworzenie zamówienia z koszyka.

        1. Weryfikuje, czy koszyk jest sfinalizowany
        2. Oblicza total
        3. Tworzy zamówienie
        4. Wysyła powiadomienie (async)
        """
        # Pobierz koszyk
        cart = self.db.execute(
            select(CartModel).where(CartModel.id == cart_id)
        ).scalar_one_or_none()

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        if cart.status != "FINALIZED":
            raise ValueError("Koszyk musi być sfinalizowany przed utworzeniem zamówienia")

        # Oblicz total
        items = self.db.execute(
            select(CartItemModel).where(CartItemModel.cart_id == cart_id)
        ).scalars().all()

        total = sum((i.price * i.quantity for i in items), Decimal("0.00"))

        if total == Decimal("0.00"):
            raise ValueError("Koszyk jest pusty")

        # Utwórz zamówienie
        order = OrderModel(
            cart_id=cart_id,
            user_id=user_id,
            status="PROCESSING",
            total=total,
        )

        created_order = self.repo.create_order(order)

        logger.info(f"Order {created_order.id} created from cart {cart_id}")

        # Wyślij powiadomienie asynchronicznie
        self.notification_service.send_order_notification(user_id, created_order.id)

        return {
            "id": created_order.id,
            "cart_id": created_order.cart_id,
            "user_id": created_order.user_id,
            "status": created_order.status,
            "total": created_order.total,
            "created_at": created_order.created_at,
        }

    def get_order(self, order_id: int, user_id: int):
        """
        Use Case: Pobranie zamówienia (Query).
        """
        order = self.repo.get_order(order_id)

        if not order:
            raise ValueError("Zamówienie nie istnieje")

        if order.user_id != user_id:
            raise PermissionError("Brak dostępu do zamówienia")

        return {
            "id": order.id,
            "cart_id": order.cart_id,
            "user_id": order.user_id,
            "status": order.status,
            "total": order.total,
            "created_at": order.created_at,
        }