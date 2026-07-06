import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models import Credit, CreditStatus, Followup, FollowupStatus, Practice, Session as PhotoSession
from app.services.email import followup_email_subject, render_followup_email, send_email
from app.services.logic import expire_followup_if_needed
from app.services.serializers import serialize_followup
from app.tasks.worker import celery_app

logger = logging.getLogger(__name__)


def _upload_url(token: str) -> str:
    settings = get_settings()
    return f"{settings.patient_portal_base_url.rstrip('/')}/{token}"


@celery_app.task(name="app.tasks.jobs.dispatch_scheduled_followups")
def dispatch_scheduled_followups():
    with SessionLocal() as db:
        followups = db.scalars(
            select(Followup).where(
                Followup.status == FollowupStatus.scheduled.value,
                Followup.send_at <= utcnow(),
            )
        ).all()
        for followup in followups:
            practice = db.scalar(select(Practice).where(Practice.id == followup.practice_id))
            session = db.scalar(select(PhotoSession).where(PhotoSession.id == followup.session_id))
            if practice is None or session is None:
                continue
            html = render_followup_email(
                practice_name=practice.name,
                patient_first_name=followup.patient_first_name,
                upload_url=_upload_url(followup.upload_token),
                message=followup.custom_message,
                reward_amount=practice.default_discount_full,
            )
            send_email(
                to_email=followup.patient_email,
                subject=followup_email_subject(practice.name),
                html=html,
            )
            followup.status = FollowupStatus.sent.value
            followup.sent_at = utcnow()
            db.add(followup)

            # Push at send-time — log-and-continue
            try:
                from app.services.push import send_followup_push
                send_followup_push(followup, session, practice.name, db)
            except Exception:
                logger.exception("Push failed for scheduled followup %s", followup.id)

        db.commit()
    return True


@celery_app.task(name="app.tasks.jobs.send_push_notification")
def send_push_notification(user_ids: list[str], title: str, body: str, data: dict | None = None) -> None:
    try:
        from app.services.push import send_push
        send_push(user_ids, title=title, body=body, data=data)
    except Exception as exc:
        logger.error("Push task failed: %s", exc)


@celery_app.task(name="app.tasks.jobs.expire_records")
def expire_records():
    with SessionLocal() as db:
        followups = db.scalars(select(Followup)).all()
        for followup in followups:
            expire_followup_if_needed(followup)
            db.add(followup)
        credits = db.scalars(
            select(Credit).where(
                Credit.status == CreditStatus.active.value,
                Credit.expires_at < utcnow(),
            )
        ).all()
        for credit in credits:
            credit.status = CreditStatus.expired.value
            db.add(credit)
        db.commit()
    return True

