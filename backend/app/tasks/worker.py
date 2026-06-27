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

# Celery autodiscovery only looks for modules named `tasks` by default.
# Our scheduled jobs live in `app.tasks.jobs`, so import them explicitly to
# ensure the worker and beat processes register those task decorators.
import app.tasks.jobs  # noqa: F401,E402
