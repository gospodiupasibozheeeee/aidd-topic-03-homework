import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {
    "update-last-prices": {
        "task": "dashboard.tasks.update_last_price",
        "schedule": settings.MARKET_UPDATE_INTERVAL,
        "options": {"expires": settings.MARKET_UPDATE_INTERVAL},
    },
}
