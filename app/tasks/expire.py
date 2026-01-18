# app/tasks/expire.py
from datetime import datetime, timezone

from app.celery_worker import celery_app
from app.data.database import SessionLocal
from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel
from app.services.lock_service import LockService
from app.utils.logging import get_logger

logger = get_logger(__name__)
lock_service = LockService()

@celery_app.task(name="app.tasks.expire.expire_carts_task")
def expire_carts_task():
    logger.info("Expire carts task started")

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        carts = (
            db.query(CartModel)
            .filter(
                CartModel.status == "ACTIVE",
                CartModel.expires_at < now,
            )
            .all()
        )

        logger.info(f"Found {len(carts)} carts to expire")

        for cart in carts:
            cart.status = "EXPIRED"
            db.add(cart)

            items = (
                db.query(CartItemModel)
                .filter(CartItemModel.cart_id == cart.id)
                .all()
            )

            for item in items:
                try:
                    lock_service.release_product_lock(
                        product_id=item.product_id,
                        cart_id=cart.id,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to release lock for product {item.product_id}: {e}"
                    )
        db.commit()

    finally:
        db.close()