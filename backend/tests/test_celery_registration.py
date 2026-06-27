from app.tasks.worker import celery_app


def test_celery_registers_scheduled_jobs():
    assert "app.tasks.jobs.dispatch_scheduled_followups" in celery_app.tasks
    assert "app.tasks.jobs.expire_records" in celery_app.tasks
