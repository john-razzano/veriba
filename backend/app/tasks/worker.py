from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("veriba", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_always_eager=settings.celery_eager,
    timezone="UTC",
    beat_schedule={
        "dispatch-scheduled-followups": {
            "task": "app.tasks.jobs.dispatch_scheduled_followups",
            "schedule": 300.0,
        },
        "expire-followups-and-credits": {
            "task": "app.tasks.jobs.expire_records",
            "schedule": 86400.0,
        },
    },
)
celery_app.autodiscover_tasks(["app.tasks"])

