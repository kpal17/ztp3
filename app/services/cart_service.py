from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel
from app.repos.cart_repo import CartRepo
from app.services.product_client import ProductClient
from app.services.lock_service import LockService
from app.utils.settings import CART_TTL_SECONDS
from app.utils.logging import get_logger

logger = get_logger(__name__)

class CartService:
    """
    Prosta implementacja cqrs i proste use case dla domeny cart
    commands (create, add, remove, finalize) modyfikuja stan
    query (get) tylko odczyt
    """

    def __init__(
        self,
        db: Session,
        product_client: ProductClient,
        lock_service: LockService,
    ):
        self.repo = CartRepo(db)
        self.product_client = product_client
        self.lock_service = lock_service

    #query - odczyt
    def get_cart(self, cart_id: int, user_id: int) -> Dict[str, Any] | None:
        cart = self.repo.get_cart(cart_id)

        if not cart:
            return None

        if cart.user_id != user_id:
            raise PermissionError("Brak dostepu do koszyka")

        #pobierz produkty z repo i oblicz total
        items = self.repo.get_cart_items(cart_id)
        total = sum((i.price * i.quantity for i in items), Decimal("0.00"))

        #dict przyksztalcany w jsona
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

    #commands
    def create_cart(self, user_id: int) -> Dict[str, Any]:
        #check czy user ma aktywny koszyk
        existing = self.repo.get_active_cart_by_user(user_id)

        if existing:
            items = self.repo.get_cart_items(existing.id)
            total = sum((i.price * i.quantity for i in items), Decimal("0.00"))

            logger.info(f"Uzytkownik o ID {user_id} ma juz aktywny koszyk {existing.id}")
            #return dicta z danymi koszyka
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

        #tworzymy nowy koszyk
        expires = datetime.now(timezone.utc) + timedelta(seconds=CART_TTL_SECONDS)

        #TTL na 15 min i version 1
        new_cart = CartModel(
            user_id=user_id,
            status="ACTIVE",
            version=1,
            expires_at=expires,
        )

        created = self.repo.create_cart(new_cart)

        logger.info(f"Utworzono nowy koszyk {created.id} dla użytkownika {user_id}")

        return {
            "cart_id": created.id,
            "user_id": created.user_id,
            "status": created.status,
            "items": [],
            "total": Decimal("0.00"),
            "expires_at": created.expires_at,
        }

    def add_product(
        self,
        user_id: int,
        cart_id: int,
        product_id: int,
        quantity: int,
    ) -> Dict[str, Any]:

        # Walidacje
        if quantity <= 0:
            raise ValueError("Ilosc musi być wieksza niz 0")

        cart = self.repo.get_cart(cart_id)

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        if cart.status != "ACTIVE":
            raise ValueError("Koszyk nie może byc modyfikowany")

        """
        # Optimistic locking, na pole wersji
        # Redis lock dla produktu
        # HTTP do product-service (walidacja + cena)
        """
        logger.info(f"Pobieranie danych produktu {product_id} z product-service")
        pdata = self.product_client.fetch_product(product_id)
        price = Decimal(str(pdata["price"]))

        # Redis lock (blokada produktu zeby nikt inny ich nie kupil)
        logger.info(f"Proba zablokowania produktu {product_id} dla koszyka {cart_id}")

        locked = self.lock_service.acquire_product_lock(
            product_id=product_id,
            cart_id=cart_id,
            ttl=CART_TTL_SECONDS,
        )

        if not locked:
            raise RuntimeError("Produkt jest już zarezerwowany przez inny koszyk")

        try:
            # Sprawdz czy produkt juz jest w koszyku
            existing_item = self.repo.get_cart_item(cart_id, product_id)

            if existing_item:
                logger.info(
                    f"Produkt {product_id} już jest w koszyku, zwiekszam ilosc "
                    f"z {existing_item.quantity} do {existing_item.quantity + quantity}"
                )
                existing_item.quantity += quantity
                existing_item.price = price  # update ceny
                self.repo.add_cart_item(existing_item)
            else:
                logger.info(f"Dodaje nowy produkt {product_id} do koszyka {cart_id}")
                self.repo.add_cart_item(
                    CartItemModel(
                        cart_id=cart_id,
                        product_id=product_id,
                        quantity=quantity,
                        price=price,
                    )
                )

            # Przedluz waznosc koszyka
            # user JEST aktywny, dodaje produkty do koszyka i nie chcemy wygasic koszyka podczas zakupow
            # kazda akcja TTL + 15 min
            new_expires = datetime.now(timezone.utc) + timedelta(seconds=CART_TTL_SECONDS
            )

            # Optimistic locking
            rowcount = self.repo.update_cart_version(
                cart_id=cart.id,
                old_version=cart.version,
                new_data={
                    "version": cart.version + 1,
                    "expires_at": new_expires,
                },
            )

            # Optimistic locking warunek na wersje
            # np w bazie update set version 2 where id 1 and version 1
            if rowcount == 0:
                self.repo.rollback()
                self.lock_service.release_product_lock(product_id, cart_id)
                raise RuntimeError(
                    "Konflikt wspolbieznosci - koszyk zostal zmodyfikowany przez inna operacje"
                )

            self.repo.commit()

            logger.info(
                f"Produkt {product_id} dodany do koszyka {cart_id}, "
                f"nowa wersja: {cart.version + 1}"
            )

            return self.get_cart(cart_id, user_id)

        except Exception as e:
            # W przypadku bledu zwolnij lock
            logger.error(f"Blad podczas dodawania produktu: {e}")
            self.lock_service.release_product_lock(product_id, cart_id)
            raise

    def remove_product(
        self,
        user_id: int,
        cart_id: int,
        product_id: int,
    ) -> Dict[str, Any]:

        cart = self.repo.get_cart(cart_id)

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        logger.info(f"Usuwanie produktu {product_id} z koszyka {cart_id}")

        #usun item i zwolnij locka
        self.repo.delete_cart_item(cart_id, product_id)
        self.lock_service.release_product_lock(product_id, cart_id)

        rowcount = self.repo.update_cart_version(
            cart_id=cart.id,
            old_version=cart.version,
            new_data={"version": cart.version + 1},
        )

        if rowcount == 0: #jesli tj 0 rows affected
            self.repo.rollback()
            raise RuntimeError(
                "Konflikt współbieżności - koszyk został zmodyfikowany przez inną operację"
            )

        self.repo.commit()

        logger.info(
            f"Produkt {product_id} usunięty z koszyka {cart_id}, "
            f"nowa wersja: {cart.version + 1}"
        )

        return self.get_cart(cart_id, user_id)

    def finalize_cart(self, user_id: int, cart_id: int) -> Dict[str, Any]:

        cart = self.repo.get_cart(cart_id)

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostepu do koszyka")

        if cart.status != "ACTIVE":
            raise ValueError("Koszyk nie jest aktywny")

        #sprawdz czy koszyk nie jest pusty
        items = self.repo.get_cart_items(cart_id)
        if not items:
            raise ValueError("Nie można finalizować pustego koszyka")

        logger.info(f"Finalizowanie koszyka {cart_id}")

        # Optimistic locking
        rowcount = self.repo.update_cart_version(
            cart_id=cart.id,
            old_version=cart.version,
            new_data={
                "status": "FINALIZED",
                "version": cart.version + 1,
            },
        )

        if rowcount == 0:
            self.repo.rollback()
            raise RuntimeError(
                "Konflikt wspolbieznosci - koszyk zostal zmodyfikowany przez inna operacje"
            )

        self.repo.commit()

        logger.info(
            f"Koszyk {cart.id} sfinalizowany nowa wersja: {cart.version + 1}"
        )

        return self.get_cart(cart_id, user_id)
