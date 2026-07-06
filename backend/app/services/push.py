"""Expo push notification sender.

Delivery stays dark until APNs key is configured in EAS.
Tokens that come back DeviceNotRegistered are automatically removed.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Followup, PushToken, Session as PhotoSession

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
CHUNK_SIZE = 100


def send_push(user_ids: list[str], title: str, body: str, data: dict | None = None) -> None:
    """Send push notifications to all tokens registered for the given user IDs."""
    if not user_ids:
        logger.info("send_push: no user_ids, skipping")
        return

    with SessionLocal() as db:
        tokens = db.scalars(
            select(PushToken).where(PushToken.user_id.in_(user_ids))
        ).all()

        logger.info("send_push: %d user(s) → %d token(s) found", len(user_ids), len(tokens))

        if not tokens:
            return

        token_map = {t.token: t for t in tokens}
        messages = [
            {"to": t.token, "title": title, "body": body, "data": data or {}}
            for t in tokens
        ]

        stale: list[str] = []
        for i in range(0, len(messages), CHUNK_SIZE):
            chunk = messages[i : i + CHUNK_SIZE]
            try:
                resp = httpx.post(EXPO_PUSH_URL, json=chunk, timeout=10)
                resp.raise_for_status()
                result_data = resp.json().get("data", [])
                logger.info(
                    "send_push: Expo responded %s — %s",
                    resp.status_code,
                    result_data,
                )
                for j, result in enumerate(result_data):
                    if (
                        result.get("status") == "error"
                        and result.get("details", {}).get("error") == "DeviceNotRegistered"
                    ):
                        stale.append(chunk[j]["to"])
            except Exception as exc:
                logger.error("send_push: chunk %d failed: %s", i // CHUNK_SIZE, exc)

        if stale:
            for raw_token in stale:
                pt = token_map.get(raw_token)
                if pt:
                    db.delete(pt)
            db.commit()
            logger.info("send_push: removed %d stale tokens", len(stale))


def send_followup_push(
    followup: Followup,
    session: PhotoSession,
    practice_name: str,
    db: Session,
) -> None:
    """Resolve the member for this followup and fire push with copy matched to session state."""
    from app.models import SessionStatus
    from app.services.logic import resolve_followup_member

    member = resolve_followup_member(followup, db)
    if not member:
        return

    if session.status == SessionStatus.pending_after.value:
        title = practice_name
        body = "Time to add your after photo — tap to upload."
        kind = "after_upload"
    else:
        title = f"{practice_name} shared your results for review"
        body = "Open the app to review and approve your case."
        kind = "approval"

    logger.info(
        "send_followup_push: followup=%s member=%s kind=%s",
        followup.id, member.id, kind,
    )
    send_push([member.id], title=title, body=body, data={"followup_id": followup.id, "kind": kind})
