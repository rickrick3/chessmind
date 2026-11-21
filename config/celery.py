import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_shutdown

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("chess_coach")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    # Gemini free-tier quotas reset at midnight Pacific time.
    "upgrade-pending-explanations": {
        "task": "analysis.tasks.upgrade_pending_explanations",
        "schedule": crontab(hour=8, minute=5),
    },
    "delete-idle-guests": {
        "task": "accounts.tasks.delete_idle_guests",
        "schedule": crontab(hour=3, minute=30, day_of_week="mon"),
    },
}


@worker_process_shutdown.connect
def _close_engine(**_kwargs):
    from analysis.engine import close_engine

    close_engine()
