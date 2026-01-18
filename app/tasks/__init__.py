#Import wszystkich tasków Celery
from app.tasks.expire import expire_carts_task

__all__ = ["expire_carts_task"]