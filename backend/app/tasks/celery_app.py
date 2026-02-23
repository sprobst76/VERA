from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "vera",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.reminder_tasks", "app.tasks.payroll_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Berlin",
    enable_utc=True,
    beat_schedule={
        # Täglich um 08:00: Erinnerungen für morgige Dienste
        "daily-shift-reminders": {
            "task": "app.tasks.reminder_tasks.send_daily_reminders",
            "schedule": crontab(hour=8, minute=0),
        },
        # Stündlich: Fällige Erinnerungen senden
        "hourly-shift-reminders": {
            "task": "app.tasks.reminder_tasks.send_hourly_reminders",
            "schedule": crontab(minute=0),
        },
        # Monatlich am 1. um 07:00: Lohnabrechnungen für Vormonat erstellen
        "monthly-payroll": {
            "task": "app.tasks.payroll_tasks.create_monthly_payrolls",
            "schedule": crontab(hour=7, minute=0, day_of_month=1),
        },
    },
)
