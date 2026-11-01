import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# All Celery options live in Django settings with the CELERY_ prefix
# (including CELERY_BEAT_SCHEDULE and MARKET_UPDATE_INTERVAL).
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
