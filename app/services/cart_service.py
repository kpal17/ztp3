# app/services/cart_service.py
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
    Serwis obsługujący Use Case'y dla domeny Cart.
    
    Zgodnie z CQRS:
    - Komendy (create, add, remove, finalize) - modyfikują stan
    - Zapytania (get) - tylko odczyt
    
    Zgodnie z SOLID:
    - Single Responsibility: tylko logika biznesowa koszyków
    - Dependency Inversion: zależy od abstrakcji (repo, client, lock)
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

    # =====================================================
    # QUERY (tylko odczyt)
    # =====================================================
    def get_cart(self, cart_id: int, user_id: int) -> Dict[str, Any] | None:
        """
        Use Case: Pobranie koszyka (Query).
        
        Args:
            cart_id: ID koszyka
            user_id: ID użytkownika (weryfikacja dostępu)
            
        Returns:
            Słownik z danymi koszyka lub None jeśli nie istnieje
            
        Raises:
            PermissionError: Gdy użytkownik nie ma dostępu do koszyka
        """
        cart = self.repo.get_cart(cart_id)

        if not cart:
            return None

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        items = self.repo.get_cart_items(cart_id)
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
    # COMMANDS (modyfikują stan)
    # =====================================================
    def create_cart(self, user_id: int) -> Dict[str, Any]:
        """
        Use Case: Utworzenie koszyka (Command).
        
        Logika:
        - Jeśli użytkownik ma już aktywny koszyk, zwraca go
        - W przeciwnym razie tworzy nowy
        
        Args:
            user_id: ID użytkownika
            
        Returns:
            Słownik z danymi koszyka
        """
        # Sprawdź, czy istnieje aktywny koszyk
        existing = self.repo.get_active_cart_by_user(user_id)

        if existing:
            items = self.repo.get_cart_items(existing.id)
            total = sum((i.price * i.quantity for i in items), Decimal("0.00"))

            logger.info(f"Użytkownik {user_id} ma już aktywny koszyk {existing.id}")

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

        # Utwórz nowy koszyk
        expires = datetime.now(timezone.utc) + timedelta(seconds=CART_TTL_SECONDS)

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
        """
        Use Case: Dodanie produktu do koszyka (Command).

        Walidacja:
        - quantity > 0
        - koszyk istnieje i należy do użytkownika
        - koszyk jest aktywny
        - produkt istnieje w product-service
        - produkt nie jest zablokowany przez inny koszyk

        Współbieżność:
        - Optimistic locking (version field)
        - Redis lock dla produktu
        
        Args:
            user_id: ID użytkownika
            cart_id: ID koszyka
            product_id: ID produktu
            quantity: Ilość produktu
            
        Returns:
            Zaktualizowany koszyk
            
        Raises:
            ValueError: Nieprawidłowe dane wejściowe
            PermissionError: Brak dostępu do koszyka
            RuntimeError: Konflikt współbieżności lub blokada produktu
        """
        # Walidacja quantity
        if quantity <= 0:
            raise ValueError("Ilość musi być większa niż 0")

        cart = self.repo.get_cart(cart_id)

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        if cart.status != "ACTIVE":
            raise ValueError("Koszyk nie może być modyfikowany")

        # HTTP → product-service (walidacja + cena)
        logger.info(f"Pobieranie danych produktu {product_id} z product-service")
        pdata = self.product_client.fetch_product(product_id)
        price = Decimal(str(pdata["price"]))

        # Redis lock (blokada produktu)
        logger.info(f"Próba zablokowania produktu {product_id} dla koszyka {cart_id}")
        locked = self.lock_service.acquire_product_lock(
            product_id=product_id,
            cart_id=cart_id,
            ttl=CART_TTL_SECONDS,
        )

        if not locked:
            raise RuntimeError("Produkt jest już zarezerwowany przez inny koszyk")

        try:
            # Sprawdź, czy produkt już jest w koszyku
            existing_item = self.repo.get_cart_item(cart_id, product_id)

            if existing_item:
                logger.info(
                    f"Produkt {product_id} już jest w koszyku, zwiększam ilość "
                    f"z {existing_item.quantity} do {existing_item.quantity + quantity}"
                )
                existing_item.quantity += quantity
                existing_item.price = price  # aktualizacja ceny
                self.repo.add_cart_item(existing_item)
            else:
                logger.info(f"Dodaję nowy produkt {product_id} do koszyka {cart_id}")
                self.repo.add_cart_item(
                    CartItemModel(
                        cart_id=cart_id,
                        product_id=product_id,
                        quantity=quantity,
                        price=price,
                    )
                )

            # Przedłuż ważność koszyka
            new_expires = datetime.now(timezone.utc) + timedelta(
                seconds=CART_TTL_SECONDS
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

            if rowcount == 0:
                self.repo.rollback()
                self.lock_service.release_product_lock(product_id, cart_id)
                raise RuntimeError(
                    "Konflikt współbieżności - koszyk został zmodyfikowany przez inną operację"
                )

            self.repo.commit()

            logger.info(
                f"Produkt {product_id} dodany do koszyka {cart_id}, "
                f"nowa wersja: {cart.version + 1}"
            )

            return self.get_cart(cart_id, user_id)

        except Exception as e:
            # W przypadku błędu zwolnij lock
            logger.error(f"Błąd podczas dodawania produktu: {e}")
            self.lock_service.release_product_lock(product_id, cart_id)
            raise

    def remove_product(
        self,
        user_id: int,
        cart_id: int,
        product_id: int,
    ) -> Dict[str, Any]:
        """
        Use Case: Usunięcie produktu z koszyka (Command).
        
        Args:
            user_id: ID użytkownika
            cart_id: ID koszyka
            product_id: ID produktu
            
        Returns:
            Zaktualizowany koszyk
            
        Raises:
            ValueError: Koszyk nie istnieje
            PermissionError: Brak dostępu do koszyka
            RuntimeError: Konflikt współbieżności
        """
        cart = self.repo.get_cart(cart_id)

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        logger.info(f"Usuwanie produktu {product_id} z koszyka {cart_id}")

        # Usuń item
        self.repo.delete_cart_item(cart_id, product_id)

        # Zwolnij blokadę
        self.lock_service.release_product_lock(product_id, cart_id)

        # Optimistic locking
        rowcount = self.repo.update_cart_version(
            cart_id=cart.id,
            old_version=cart.version,
            new_data={"version": cart.version + 1},
        )

        if rowcount == 0:
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
        """
        Use Case: Finalizacja koszyka (Command).
        
        Zmienia status na FINALIZED - gotowy do utworzenia zamówienia.
        
        Args:
            user_id: ID użytkownika
            cart_id: ID koszyka
            
        Returns:
            Sfinalizowany koszyk
            
        Raises:
            ValueError: Koszyk nie istnieje, nie jest aktywny lub jest pusty
            PermissionError: Brak dostępu do koszyka
            RuntimeError: Konflikt współbieżności
        """
        cart = self.repo.get_cart(cart_id)

        if not cart:
            raise ValueError("Koszyk nie istnieje")

        if cart.user_id != user_id:
            raise PermissionError("Brak dostępu do koszyka")

        if cart.status != "ACTIVE":
            raise ValueError("Koszyk nie jest aktywny")

        # Sprawdź, czy koszyk nie jest pusty
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
                "Konflikt współbieżności - koszyk został zmodyfikowany przez inną operację"
            )

        self.repo.commit()

        logger.info(
            f"Koszyk {cart.id} sfinalizowany, nowa wersja: {cart.version + 1}"
        )

        return self.get_cart(cart_id, user_id)
