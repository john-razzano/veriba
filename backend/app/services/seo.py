import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import Practice, Session
from app.services.logic import slugify

SEO_TEMPLATES = [
    "See verified {treatment} results at {practice} in {location}. {details}. Before photo at consultation, after captured {timeframe} post-treatment.",
    "Real {treatment} before and after from {practice}, {location}. {details}. Verified with Veriba chain-of-custody authentication.",
    "{practice} in {location} shares verified {treatment} results. {details}. Every photo cryptographically signed and unaltered.",
]


def _detail_slug(session: Session) -> str:
    if session.treatment_details:
        return slugify(session.treatment_details)
    parts = re.split(r"\s+[–-]\s+|\s+", session.treatment)
    tail = parts[-2:] if len(parts) > 1 else parts
    return slugify("-".join(tail))


def _next_sequence(db: Session, prefix: str) -> int:
    existing = db.scalars(select(Session.seo_filename).where(Session.seo_filename.like(f"{prefix}-%"))).all()
    seq = 0
    for filename in existing:
        if not filename:
            continue
        match = re.search(r"-(\d{3})\.jpg$", filename)
        if match:
            seq = max(seq, int(match.group(1)))
    return seq + 1


def generate_seo(db: Session, *, session: Session, practice: Practice) -> dict[str, str]:
    when = session.published_at or session.captured_at or utcnow()
    prefix = "-".join(
        [
            slugify(session.treatment),
            _detail_slug(session),
            practice.widget_slug,
            slugify(practice.location),
            when.strftime("%Y-%m"),
        ]
    )
    sequence = _next_sequence(db, prefix)
    sequence_label = f"{sequence:03d}"
    filename = f"{prefix}-{sequence_label}.jpg"
    url_slug = f"{prefix}-{sequence_label}"
    month_label = when.strftime("%B %Y")
    details = session.treatment_details or "Verified before and after photography."
    timeframe = "after recovery"
    template_index = session.seo_template_variant % len(SEO_TEMPLATES)
    meta_description = SEO_TEMPLATES[template_index].format(
        treatment=session.treatment,
        practice=practice.name,
        location=practice.location,
        details=details,
        timeframe=timeframe,
    )
    title = f"{session.treatment} Before & After | {practice.name}, {practice.location}"
    alt_text = (
        f"{session.treatment} before and after at {practice.name} "
        f"{practice.location} {month_label}"
    )
    return {
        "title": title,
        "alt_text": alt_text,
        "meta_description": meta_description,
        "filename": filename,
        "url_slug": url_slug,
        "template_variant": template_index + 1,
    }

