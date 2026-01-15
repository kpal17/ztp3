# app/services/notification_service.py
from app.celery_worker import celery_app
from app.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationService:
    """
    Serwis do wysyłania powiadomień.
    Używa Celery do asynchronicznego przetwarzania.
    """

    @staticmethod
    def send_order_notification(user_id: int, order_id: int):
        """
        Wysyła powiadomienie o rozpoczęciu realizacji zamówienia.
        """
        send_order_notification_task.delay(user_id, order_id)


@celery_app.task(name="app.services.notification_service.send_order_notification_task")
def send_order_notification_task(user_id: int, order_id: int):
    """
    Celery task - w prawdziwym systemie wysłałby email/SMS/push.
    Teraz tylko loguje.
    """
    logger.info(f"[NOTIFICATION] User {user_id}: Order {order_id} is being processed")

    # W rzeczywistości tutaj byłby np.:
    # - email client (SendGrid, AWS SES)
    # - SMS gateway (Twilio)
    # - push notification (Firebase)

    return {"user_id": user_id, "order_id": order_id, "status": "sent"}