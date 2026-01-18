from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel

class CartRepo:

    def __init__(self, db: Session):
        self.db = db

    def get_cart(self, cart_id: int) -> CartModel | None:
        return self.db.execute(
            select(CartModel).where(CartModel.id == cart_id)
        ).scalar_one_or_none()

    def get_cart_items(self, cart_id: int) -> list[CartItemModel]:
        return self.db.execute(
            select(CartItemModel).where(CartItemModel.cart_id == cart_id)
        ).scalars().all()

    def get_active_cart_by_user(self, user_id: int) -> CartModel | None:
        #Pobierz aktywny koszyk użytkownika jesli istnieje
        return self.db.execute(
            select(CartModel).where(
                CartModel.user_id == user_id,
                CartModel.status == "ACTIVE",
            )
        ).scalar_one_or_none()

    def create_cart(self, cart: CartModel) -> CartModel:
        self.db.add(cart)
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def get_cart_item(self, cart_id: int, product_id: int) -> CartItemModel | None:
        #Pobierz konkretny produkt z koszyka
        return self.db.execute(
            select(CartItemModel).where(
                CartItemModel.cart_id == cart_id,
                CartItemModel.product_id == product_id,
            )
        ).scalar_one_or_none()

    def add_cart_item(self, item: CartItemModel) -> None:
        #dodaj lub zaktualizuj produkt w koszyku
        self.db.add(item)

    def delete_cart_item(self, cart_id: int, product_id: int) -> None:
        self.db.execute(
            delete(CartItemModel).where(
                CartItemModel.cart_id == cart_id,
                CartItemModel.product_id == product_id,
            )
        )

    def update_cart_version(self, cart_id: int, old_version: int, new_data: dict) -> int:
        """
        Optimistic locking
        old_version: Oczekiwana wersja (dla optimistic locking)
        new_data: dict z danymi do aktualizacji (np {"version": 2, "status": "FINALIZED"})
        """
        stmt = (
            update(CartModel)
            .where(
                CartModel.id == cart_id,
                CartModel.version == old_version,
            )
            .values(**new_data)
        )
        res = self.db.execute(stmt)
        return res.rowcount

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
