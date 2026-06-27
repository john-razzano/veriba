import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def followup_email_subject(practice_name: str) -> str:
    return f"Your visit to {practice_name} — share your results"


def render_followup_email(
    *,
    practice_name: str,
    patient_first_name: str | None,
    upload_url: str,
    message: str | None,
    reward_amount: int,
) -> str:
    greeting = f"Hi {patient_first_name}," if patient_first_name else "Hi,"
    body = (
        message
        or f"Your results may be ready. Upload your after photo and claim your ${reward_amount} reward."
    )
    return (
        f"<p>{greeting}</p>"
        f"<p>{body}</p>"
        f'<p><a href="{upload_url}">Upload your after photo</a></p>'
        f"<p>Thank you,<br>{practice_name} via Veriba</p>"
    )


def send_email(*, to_email: str, subject: str, html: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        logger.info("Email stub delivery to %s with subject %s", to_email, subject)
        return

    payload = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}
    with httpx.Client(timeout=15) as client:
        response = client.post("https://api.resend.com/emails", json=payload, headers=headers)
        response.raise_for_status()

