# app/celery_worker.py
from celery import Celery
import os

BROKER = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

celery_app = Celery(
    "cart",
    broker=BROKER,
    backend=RESULT_BACKEND,
)

#jawny import zeby celery je zarejestrowal
celery_app.conf.imports = (
    "app.tasks.expire",
    "app.services.notification_service",
)

#CELERY BEAT SCHEDULE, harmonogram cron
celery_app.conf.beat_schedule = {
    "expire-carts-every-minute": {
        "task": "app.tasks.expire.expire_carts_task",
        "schedule": 60.0,  # co 60 sekund
    },
}

celery_app.conf.timezone = "UTC"