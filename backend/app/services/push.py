"""Expo push notification sender.

Delivery stays dark until APNs key is configured in EAS.
Tokens that come back DeviceNotRegistered are automatically removed.
"""

import logging

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import PushToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
CHUNK_SIZE = 100


def send_push(user_ids: list[str], title: str, body: str, data: dict | None = None) -> None:
    """Send push notifications to all tokens registered for the given user IDs."""
    if not user_ids:
        return

    with SessionLocal() as db:
        tokens = db.scalars(
            select(PushToken).where(PushToken.user_id.in_(user_ids))
        ).all()
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
                for j, result in enumerate(resp.json().get("data", [])):
                    if (
                        result.get("status") == "error"
                        and result.get("details", {}).get("error") == "DeviceNotRegistered"
                    ):
                        stale.append(chunk[j]["to"])
            except Exception as exc:
                logger.error("Push chunk %d failed: %s", i // CHUNK_SIZE, exc)

        if stale:
            for raw_token in stale:
                pt = token_map.get(raw_token)
                if pt:
                    db.delete(pt)
            db.commit()
            logger.info("Removed %d stale push tokens", len(stale))
