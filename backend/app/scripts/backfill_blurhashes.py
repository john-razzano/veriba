"""Backfill before_blurhash / after_blurhash for sessions and avatar_blurhash for practices.

Run once after deploying migration 0005:
    docker compose exec fastapi python -m app.scripts.backfill_blurhashes
"""

import logging

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Practice, Session
from app.services.images import compute_blurhash
from app.services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run() -> dict:
    storage = get_storage()
    sessions_done = 0
    sessions_skipped = 0
    avatars_done = 0
    avatars_skipped = 0

    with SessionLocal() as db:
        # Sessions with image keys but missing hashes
        sessions = db.scalars(
            select(Session).where(
                (Session.before_image_key.is_not(None) & Session.before_blurhash.is_(None))
                | (Session.after_image_key.is_not(None) & Session.after_blurhash.is_(None))
            )
        ).all()

        for session in sessions:
            updated = False

            if session.before_image_key and not session.before_blurhash:
                try:
                    data = storage.get_bytes(session.before_image_key)
                    if data:
                        session.before_blurhash = compute_blurhash(data)
                        updated = True
                except Exception as exc:
                    logger.warning("before %s: %s", session.id[:8], exc)

            if session.after_image_key and not session.after_blurhash:
                try:
                    data = storage.get_bytes(session.after_image_key)
                    if data:
                        session.after_blurhash = compute_blurhash(data)
                        updated = True
                except Exception as exc:
                    logger.warning("after %s: %s", session.id[:8], exc)

            if updated:
                db.add(session)
                sessions_done += 1
            else:
                sessions_skipped += 1

        # Practices with avatar but missing hash
        practices = db.scalars(
            select(Practice).where(
                Practice.avatar_key.is_not(None),
                Practice.avatar_blurhash.is_(None),
            )
        ).all()

        for practice in practices:
            try:
                data = storage.get_bytes(practice.avatar_key)
                if data:
                    practice.avatar_blurhash = compute_blurhash(data)
                    db.add(practice)
                    avatars_done += 1
            except Exception as exc:
                logger.warning("avatar %s: %s", practice.id[:8], exc)
                avatars_skipped += 1

        db.commit()

    return {
        "sessions_backfilled": sessions_done,
        "sessions_already_complete": sessions_skipped,
        "avatars_backfilled": avatars_done,
        "avatars_skipped": avatars_skipped,
    }


def main() -> None:
    result = run()
    print("Blurhash backfill complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
