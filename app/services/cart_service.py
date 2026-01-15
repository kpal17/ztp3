from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, update, delete

from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel
from app.utils.settings import CART_TTL_SECONDS
from app.utils.logging import get_logger

from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel

logger = get_logger(__name__)


class CartService:
    def __init__(self, db, product_client, lock_service):
        self.db = db
        self.product_client = product_client
        self.lock_service = lock_service

    # =====================================================
    # QUERY
    # =====================================================
    def get_cart(self, cart_id: int, user_id: int):
        cart = self.db.execute(
            select(CartModel).where(CartModel.id == cart_id)
        ).scalar_one_or_none()

        if not cart:
            return None

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        items = self.db.execute(
            select(CartItemModel).where(CartItemModel.cart_id == cart_id)
        ).scalars().all()

        total = sum((i.price * i.quantity for i in items), Decimal("0.00"))

        return {
            "cart_id": cart.id,
            "user_id": cart.user_id,
            "status": cart.status,
            "items": [
                {
                    "product_id": i.product_id,
                    "quantity": i.quantity,
                    "price": i.price,
                }
                for i in items
            ],
            "total": total,
            "expires_at": cart.expires_at,
        }

    # =====================================================
    # COMMANDS
    # =====================================================
    def create_cart(self, user_id: int):
        existing = self.db.execute(
            select(CartModel).where(
                CartModel.user_id == user_id,
                CartModel.status == "ACTIVE",
            )
        ).scalar_one_or_none()

        if existing:
            items = self.db.execute(
                select(CartItemModel).where(CartItemModel.cart_id == existing.id)
            ).scalars().all()

            total = sum((i.price * i.quantity for i in items), Decimal("0.00"))

            return {
                "cart_id": existing.id,
                "user_id": existing.user_id,
                "status": existing.status,
                "items": [
                    {
                        "product_id": i.product_id,
                        "quantity": i.quantity,
                        "price": i.price,
                    }
                    for i in items
                ],
                "total": total,
                "expires_at": existing.expires_at,
            }

        expires = datetime.now(timezone.utc) + timedelta(seconds=CART_TTL_SECONDS)

        new_cart = CartModel(
            user_id=user_id,
            status="ACTIVE",
            version=1,
            expires_at=expires,
        )

        self.db.add(new_cart)
        self.db.commit()
        self.db.refresh(new_cart)

        return {
            "cart_id": new_cart.id,
            "user_id": new_cart.user_id,
            "status": new_cart.status,
            "items": [],
            "total": Decimal("0.00"),
            "expires_at": new_cart.expires_at,
        }

    def add_product(
        self,
        user_id: int,
        cart_id: int,
        product_id: int,
        quantity: int,
    ):
        cart = self.db.execute(
            select(CartModel).where(CartModel.id == cart_id)
        ).scalar_one_or_none()

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        if cart.status != "ACTIVE":
            raise ValueError("Koszyk nie może być modyfikowany")

        # HTTP → product-service
        pdata = self.product_client.fetch_product(product_id)
        price = Decimal(str(pdata["price"]))

        # Redis lock
        locked = self.lock_service.acquire_product_lock(
            product_id=product_id,
            cart_id=cart_id,
            ttl=CART_TTL_SECONDS,
        )

        if not locked:
            raise RuntimeError("Produkt jest już zarezerwowany")

        existing_item = self.db.execute(
            select(CartItemModel).where(
                CartItemModel.cart_id == cart_id,
                CartItemModel.product_id == product_id,
            )
        ).scalar_one_or_none()

        if existing_item:
            existing_item.quantity += quantity
            existing_item.price = price
            self.db.add(existing_item)
        else:
            self.db.add(
                CartItemModel(
                    cart_id=cart_id,
                    product_id=product_id,
                    quantity=quantity,
                    price=price,
                )
            )

        cart.expires_at = datetime.now(timezone.utc) + timedelta(seconds=CART_TTL_SECONDS)

        stmt = (
            update(CartModel)
            .where(
                CartModel.id == cart.id,
                CartModel.version == cart.version,
            )
            .values(
                version=cart.version + 1,
                expires_at=cart.expires_at,
            )
        )

        res = self.db.execute(stmt)

        if res.rowcount == 0:
            self.db.rollback()
            self.lock_service.release_product_lock(product_id, cart_id)
            raise RuntimeError("Konflikt współbieżności")

        self.db.commit()

        return self.get_cart(cart_id, user_id)

    def remove_product(
        self,
        user_id: int,
        cart_id: int,
        product_id: int,
    ):
        cart = self.db.execute(
            select(CartModel).where(CartModel.id == cart_id)
        ).scalar_one_or_none()

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        self.db.execute(
            delete(CartItemModel).where(
                CartItemModel.cart_id == cart_id,
                CartItemModel.product_id == product_id,
            )
        )

        self.lock_service.release_product_lock(product_id, cart_id)

        stmt = (
            update(CartModel)
            .where(
                CartModel.id == cart.id,
                CartModel.version == cart.version,
            )
            .values(version=cart.version + 1)
        )

        res = self.db.execute(stmt)
        if res.rowcount == 0:
            self.db.rollback()
            raise RuntimeError("Konflikt współbieżności")

        self.db.commit()

        return self.get_cart(cart_id, user_id)

    def finalize_cart(self, user_id: int, cart_id: int):
        cart = self.db.execute(
            select(CartModel).where(CartModel.id == cart_id)
        ).scalar_one_or_none()

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        if cart.status != "ACTIVE":
            raise ValueError("Koszyk nie jest aktywny")

        stmt = (
            update(CartModel)
            .where(
                CartModel.id == cart.id,
                CartModel.version == cart.version,
            )
            .values(
                status="FINALIZED",
                version=cart.version + 1,
            )
        )

        res = self.db.execute(stmt)
        if res.rowcount == 0:
            self.db.rollback()
            raise RuntimeError("Konflikt współbieżności")

        self.db.commit()

        logger.info(f"Koszyk {cart.id} sfinalizowany")

        return self.get_cart(cart_id, user_id)
