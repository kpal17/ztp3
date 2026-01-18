from app.celery_worker import celery_app
from app.utils.logging import get_logger

logger = get_logger(__name__)

class NotificationService:

    @staticmethod
    def send_order_notification(user_id: int, order_id: int):
        #wyslij powiadomienie o rozpoczeciu realizacji zamowienia
        send_order_notification_task.delay(user_id, order_id)

@celery_app.task(name="app.services.notification_service.send_order_notification_task")
def send_order_notification_task(user_id: int, order_id: int):
    #celery task, worker w tle
    logger.info(f"[NOTIFICATION] User {user_id}: Order {order_id} is being processed")
    return {"user_id": user_id, "order_id": order_id, "status": "sent"}