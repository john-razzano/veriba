from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from app.core.security import hash_password, sha256_hexdigest, utcnow
from app.db.session import SessionLocal
from app.models import (
    ConsentTier,
    Credit,
    CreditStatus,
    ObscureMode,
    Practice,
    RefreshToken,
    Role,
    Session,
    SessionCategory,
    SessionStatus,
    User,
)
from app.services.images import compress_for_web
from app.services.logic import build_publish_hash, derive_initials, normalize_website
from app.services.storage import get_storage

DEMO_PASSWORD = "veriba-demo-2026"
DEMO_EMAIL_DOMAIN = "veriba-demo.studio"
DEMO_EMAIL_SUFFIXES = {
    "aster-demo": "aster",
    "meridian-demo": "meridian",
    "solstice-demo": "solstice",
    "veriba-atelier": "atelier",
}
SEED_ASSETS_DIR = Path(__file__).resolve().parent / "seed_assets"
SMOKE_EMAIL_PREFIXES = ("gallery-test-", "frontend-test-", "medspa-test-")
DEMO_NAME_SUFFIX = " Demo"
DEMO_TAG = "VERIBA DEMO"


@dataclass(frozen=True)
class DemoTheme:
    top: tuple[int, int, int]
    bottom: tuple[int, int, int]
    glow: tuple[int, int, int]
    silhouette: tuple[int, int, int]
    accent: tuple[int, int, int]


@dataclass(frozen=True)
class DemoCreditSpec:
    amount: int
    status: str
    days_until_expiry: int
    redeemed_by: str | None = None
    void_reason: str | None = None


@dataclass(frozen=True)
class DemoSessionSpec:
    patient_initials: str
    treatment: str
    category: str
    published: bool
    consent_tier: str
    obscure_mode: str
    treatment_details: str
    page_views: int
    tagline: str
    credit: DemoCreditSpec | None = None
    # Real photography (filenames under seed_assets/). When set, these are
    # loaded instead of generating illustrative placeholder art.
    before_asset: str | None = None
    after_asset: str | None = None


@dataclass(frozen=True)
class DemoPracticeSpec:
    name: str
    slug: str
    location: str
    website: str
    owner_name: str
    owner_email: str
    theme: DemoTheme
    sessions: tuple[DemoSessionSpec, ...] = field(default_factory=tuple)


DEMO_PRACTICES: tuple[DemoPracticeSpec, ...] = (
    DemoPracticeSpec(
        name="Atelier Aster Demo",
        slug="aster-demo",
        location="Beverly Hills, CA",
        website="https://aster-demo.veriba.local",
        owner_name="Sienna Hart",
        owner_email="owner+aster@veriba-demo.studio",
        theme=DemoTheme(
            top=(247, 236, 231),
            bottom=(214, 181, 173),
            glow=(255, 231, 214),
            silhouette=(214, 164, 150),
            accent=(128, 86, 80),
        ),
        sessions=(
            DemoSessionSpec(
                patient_initials="AL",
                treatment="Lip Hydration Balance",
                category=SessionCategory.fillers.value,
                published=True,
                consent_tier=ConsentTier.full.value,
                obscure_mode=ObscureMode.none.value,
                treatment_details="A softly volumized filler outcome with emphasis on hydration, vermilion border definition, and an editorially polished finish.",
                page_views=124,
                tagline="Soft volume and proportion refinement",
                credit=DemoCreditSpec(amount=150, status=CreditStatus.active.value, days_until_expiry=70),
            ),
            DemoSessionSpec(
                patient_initials="MR",
                treatment="Jawline Definition Edit",
                category=SessionCategory.fillers.value,
                published=True,
                consent_tier=ConsentTier.partial.value,
                obscure_mode=ObscureMode.eyes.value,
                treatment_details="A contour-focused filler session with subtle structural lift through the lateral jawline and chin transition.",
                page_views=88,
                tagline="Sharper structure with a softened finish",
                credit=DemoCreditSpec(
                    amount=75,
                    status=CreditStatus.redeemed.value,
                    days_until_expiry=60,
                    redeemed_by="Front Desk",
                ),
            ),
            DemoSessionSpec(
                patient_initials="JP",
                treatment="Temple Support Planning",
                category=SessionCategory.other.value,
                published=False,
                consent_tier=ConsentTier.full.value,
                obscure_mode=ObscureMode.none.value,
                treatment_details="A pending internal planning session prepared for future upload and publication.",
                page_views=12,
                tagline="Awaiting after imagery",
                credit=None,
            ),
        ),
    ),
    DemoPracticeSpec(
        name="Meridian Skin Demo",
        slug="meridian-demo",
        location="Austin, TX",
        website="https://meridian-demo.veriba.local",
        owner_name="Noah Vale",
        owner_email="owner+meridian@veriba-demo.studio",
        theme=DemoTheme(
            top=(241, 241, 233),
            bottom=(194, 196, 176),
            glow=(232, 226, 184),
            silhouette=(168, 173, 142),
            accent=(111, 118, 89),
        ),
        sessions=(
            DemoSessionSpec(
                patient_initials="ES",
                treatment="Morpheus8 Texture Reset",
                category=SessionCategory.skin.value,
                published=True,
                consent_tier=ConsentTier.full.value,
                obscure_mode=ObscureMode.none.value,
                treatment_details="A resurfacing-focused series positioned around smoothness, tonal evening, and a more luminous camera-ready finish.",
                page_views=151,
                tagline="Texture, tone, and luminosity",
                credit=DemoCreditSpec(amount=150, status=CreditStatus.active.value, days_until_expiry=84),
            ),
            DemoSessionSpec(
                patient_initials="TS",
                treatment="Laser Tone Evening",
                category=SessionCategory.skin.value,
                published=True,
                consent_tier=ConsentTier.full_blur.value,
                obscure_mode=ObscureMode.full.value,
                treatment_details="A tone-corrective laser outcome showcased with a fully blurred identity treatment and a polished editorial crop.",
                page_views=102,
                tagline="Evened tone and softened texture",
                credit=DemoCreditSpec(
                    amount=25,
                    status=CreditStatus.voided.value,
                    days_until_expiry=45,
                    void_reason="Demo reward voided after duplicate scheduling",
                ),
            ),
            DemoSessionSpec(
                patient_initials="BC",
                treatment="Post-Peel Recovery Check",
                category=SessionCategory.skin.value,
                published=False,
                consent_tier=ConsentTier.full.value,
                obscure_mode=ObscureMode.none.value,
                treatment_details="An internal recovery check session waiting on final after imagery.",
                page_views=8,
                tagline="Queued for next capture",
                credit=None,
            ),
        ),
    ),
    DemoPracticeSpec(
        name="Solstice Lift Demo",
        slug="solstice-demo",
        location="Miami, FL",
        website="https://solstice-demo.veriba.local",
        owner_name="Camila Frost",
        owner_email="owner+solstice@veriba-demo.studio",
        theme=DemoTheme(
            top=(239, 233, 245),
            bottom=(203, 186, 209),
            glow=(241, 224, 217),
            silhouette=(188, 146, 162),
            accent=(120, 83, 109),
        ),
        sessions=(
            DemoSessionSpec(
                patient_initials="LN",
                treatment="Brow Lift Soft Focus",
                category=SessionCategory.botox.value,
                published=True,
                consent_tier=ConsentTier.full.value,
                obscure_mode=ObscureMode.none.value,
                treatment_details="A neurotoxin-led brow balance result presented with a light editorial crop and lifted eye framing.",
                page_views=134,
                tagline="Light lift with cleaner framing",
                credit=DemoCreditSpec(amount=150, status=CreditStatus.active.value, days_until_expiry=90),
            ),
            DemoSessionSpec(
                patient_initials="DV",
                treatment="Forehead Smoothing Study",
                category=SessionCategory.botox.value,
                published=True,
                consent_tier=ConsentTier.partial.value,
                obscure_mode=ObscureMode.eyes.value,
                treatment_details="A restrained smoothing result oriented toward motion-softening and elegant line reduction.",
                page_views=97,
                tagline="Softer lines without losing character",
                credit=DemoCreditSpec(
                    amount=75,
                    status=CreditStatus.redeemed.value,
                    days_until_expiry=72,
                    redeemed_by="Concierge Team",
                ),
            ),
            DemoSessionSpec(
                patient_initials="RR",
                treatment="Maintenance Visit Queue",
                category=SessionCategory.botox.value,
                published=False,
                consent_tier=ConsentTier.full.value,
                obscure_mode=ObscureMode.none.value,
                treatment_details="A maintenance appointment placeholder waiting on post-visit imagery.",
                page_views=6,
                tagline="Prepared for next upload",
                credit=None,
            ),
        ),
    ),
    DemoPracticeSpec(
        name="Veriba Atelier",
        slug="veriba-atelier",
        location="Newport Beach, CA",
        website="https://atelier.veriba.studio",
        owner_name="Elena Marsh",
        owner_email="owner+atelier@veriba-demo.studio",
        theme=DemoTheme(
            top=(240, 235, 228),
            bottom=(201, 187, 168),
            glow=(232, 214, 197),
            silhouette=(181, 103, 45),
            accent=(45, 79, 94),
        ),
        sessions=(
            DemoSessionSpec(
                patient_initials="KZ", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Structured lip filler with balanced upper-to-lower ratio, photographed in controlled studio light.",
                page_views=241, tagline="Balanced volume, natural finish",
                before_asset="kenz-lip-filler_before.jpg", after_asset="kenz-lip-filler_after.jpg"),
            DemoSessionSpec(
                patient_initials="KM", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Full-face refresh anchored by subtle lip augmentation and perioral support.",
                page_views=187, tagline="Soft augmentation, full-face harmony",
                before_asset="kenz-lip-filler-4_before.jpg", after_asset="kenz-lip-filler-4_after.jpg"),
            DemoSessionSpec(
                patient_initials="LU", treatment="Under-Eye Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Tear-trough correction reducing under-eye hollowing and shadow.",
                page_views=163, tagline="Brighter, rested under-eyes",
                before_asset="lush-under-eye_before.jpg", after_asset="lush-under-eye_after.jpg"),
            DemoSessionSpec(
                patient_initials="LL", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Definition-first lip filler with emphasis on the cupid's bow and vermilion border.",
                page_views=154, tagline="Defined borders, fuller profile",
                before_asset="lush-lip-filler_before.jpg", after_asset="lush-lip-filler_after.jpg"),
            DemoSessionSpec(
                patient_initials="LM", treatment="Microneedling", category=SessionCategory.skin.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Collagen-induction series improving texture, tone, and overall skin quality.",
                page_views=142, tagline="Refined texture after three sessions",
                before_asset="lush-microneedling_before.jpg", after_asset="lush-microneedling_after.jpg"),
            DemoSessionSpec(
                patient_initials="LT", treatment="PDO Threads", category=SessionCategory.other.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="PDO thread lift restoring mid-face support with visible lip and cheek lift.",
                page_views=133, tagline="Lifted contours without surgery",
                before_asset="lush-pdo-threads_before.jpg", after_asset="lush-pdo-threads_after.jpg"),
            DemoSessionSpec(
                patient_initials="LR", treatment="Liquid Rhinoplasty", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Non-surgical rhinoplasty smoothing the dorsal profile with structured filler.",
                page_views=228, tagline="Straightened profile in one visit",
                before_asset="lush-rhinoplasty-1_before.jpg", after_asset="lush-rhinoplasty-1_after.jpg"),
            DemoSessionSpec(
                patient_initials="LS", treatment="Liquid Rhinoplasty", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Bridge and tip refinement via non-surgical filler rhinoplasty.",
                page_views=119, tagline="Refined tip, smoother bridge",
                before_asset="lush-rhinoplasty-3_before.jpg", after_asset="lush-rhinoplasty-3_after.jpg"),
            DemoSessionSpec(
                patient_initials="AV", treatment="Under-Eye Rejuvenation", category=SessionCategory.skin.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Under-eye rejuvenation softening fine lines and puffiness around the orbital area.",
                page_views=98, tagline="Smoother, firmer eye area",
                before_asset="stock-under-eye_before.jpg", after_asset="stock-under-eye_after.jpg"),
            DemoSessionSpec(
                patient_initials="AR", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Conservative lip enhancement preserving natural shape while adding central volume.",
                page_views=176, tagline="Natural shape, added volume",
                before_asset="stock-lip-filler_before.jpg", after_asset="stock-lip-filler_after.jpg"),
            DemoSessionSpec(
                patient_initials="CT", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Side-profile lip projection with hydrated, glossy finish at two weeks.",
                page_views=152, tagline="Projection with a soft finish",
                before_asset="catalyst-lip-filler_before.jpg", after_asset="catalyst-lip-filler_after.jpg"),
            DemoSessionSpec(
                patient_initials="RR", treatment="BBL + Moxi Laser", category=SessionCategory.skin.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Combined BBL and Moxi laser series clearing sun damage and evening tone.",
                page_views=204, tagline="Sun damage visibly cleared",
                before_asset="refine-bbl-moxi_before.jpg", after_asset="refine-bbl-moxi_after.jpg"),
            DemoSessionSpec(
                patient_initials="RB", treatment="BBL Laser", category=SessionCategory.skin.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="BBL corrective series reducing redness and diffuse pigment.",
                page_views=117, tagline="Calmer, clearer complexion",
                before_asset="refine-bbl-laser_before.jpg", after_asset="refine-bbl-laser_after.jpg"),
            DemoSessionSpec(
                patient_initials="RM", treatment="BBL Melasma Treatment", category=SessionCategory.skin.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Targeted BBL protocol lifting melasma across the forehead.",
                page_views=109, tagline="Forehead pigment lifted",
                before_asset="refine-bbl-melasma_before.jpg", after_asset="refine-bbl-melasma_after.jpg"),
            DemoSessionSpec(
                patient_initials="WR", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Revanesse lip filler restoring border definition and even fullness.",
                page_views=138, tagline="Even fullness with Revanesse",
                before_asset="woodbury-lip-revanesse_before.jpg", after_asset="woodbury-lip-revanesse_after.jpg"),
            DemoSessionSpec(
                patient_initials="WL", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Progressive lip filler documented across the treatment arc.",
                page_views=126, tagline="A documented progression",
                before_asset="woodbury-lip-fillers_before.jpg", after_asset="woodbury-lip-fillers_after.jpg"),
            DemoSessionSpec(
                patient_initials="WV", treatment="Lip Filler", category=SessionCategory.fillers.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Volume-focused lip filler shown in matched profile views.",
                page_views=131, tagline="Volume, profile-matched",
                before_asset="woodbury-lip-volume_before.jpg", after_asset="woodbury-lip-volume_after.jpg"),
            DemoSessionSpec(
                patient_initials="PT", treatment="PDO Thread Lift", category=SessionCategory.other.value,
                published=True, consent_tier=ConsentTier.full.value, obscure_mode=ObscureMode.none.value,
                treatment_details="Full-face PDO thread lift with visible jawline and mid-face repositioning.",
                page_views=195, tagline="Repositioned, still natural",
                before_asset="pdo-threads_before.jpg", after_asset="pdo-threads_after.jpg"),
        ),
    ),
)


def is_synthetic_user_email(email: str | None) -> bool:
    if not email:
        return False
    lowered = email.lower()
    return (
        lowered.endswith("@example.com")
        or lowered.endswith(DEMO_EMAIL_DOMAIN)
        or any(prefix in lowered for prefix in SMOKE_EMAIL_PREFIXES)
    )


def is_synthetic_practice_name(name: str | None) -> bool:
    return bool(name and name.endswith(DEMO_NAME_SUFFIX))


def synthetic_practice_slugs() -> set[str]:
    return {item.slug for item in DEMO_PRACTICES}


def list_synthetic_practice_ids(db: OrmSession) -> list[str]:
    owner_emails_by_practice: dict[str, list[str]] = {}
    for user in db.scalars(select(User)).all():
        owner_emails_by_practice.setdefault(user.practice_id, []).append(user.email.lower())

    ids: list[str] = []
    for practice in db.scalars(select(Practice)).all():
        owner_emails = owner_emails_by_practice.get(practice.id, [])
        if (
            practice.widget_slug in synthetic_practice_slugs()
            or is_synthetic_practice_name(practice.name)
            or any(is_synthetic_user_email(email) for email in owner_emails)
        ):
            ids.append(practice.id)
    return ids


def delete_synthetic_records(db: OrmSession) -> dict[str, int]:
    practice_ids = list_synthetic_practice_ids(db)
    if not practice_ids:
        return {
            "practices": 0,
            "users": 0,
            "sessions": 0,
            "credits": 0,
            "refresh_tokens": 0,
            "storage_objects": 0,
        }

    users = db.scalars(select(User).where(User.practice_id.in_(practice_ids))).all()
    user_ids = [user.id for user in users]
    sessions = db.scalars(select(Session).where(Session.practice_id.in_(practice_ids))).all()
    session_ids = [session.id for session in sessions]
    credits = db.scalars(select(Credit).where(Credit.practice_id.in_(practice_ids))).all()
    refresh_tokens = (
        db.scalars(select(RefreshToken).where(RefreshToken.user_id.in_(user_ids))).all() if user_ids else []
    )

    storage = get_storage()
    storage_objects = 0
    for practice_id in practice_ids:
        storage_objects += storage.delete_prefix(practice_id)

    db.execute(update(Practice).where(Practice.id.in_(practice_ids)).values(owner_id=None))

    for credit in credits:
        db.delete(credit)
    for token in refresh_tokens:
        db.delete(token)
    for session in sessions:
        db.delete(session)
    for user in users:
        db.delete(user)
    practices = db.scalars(select(Practice).where(Practice.id.in_(practice_ids))).all()
    for practice in practices:
        db.delete(practice)

    db.commit()

    return {
        "practices": len(practice_ids),
        "users": len(user_ids),
        "sessions": len(session_ids),
        "credits": len(credits),
        "refresh_tokens": len(refresh_tokens),
        "storage_objects": storage_objects,
    }


def _lerp_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    return tuple(
        int(start[index] + (end[index] - start[index]) * ratio)
        for index in range(3)
    )


def _load_font(size: int):
    for candidate in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient_canvas(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line((0, y, width, y), fill=_lerp_color(top, bottom, y / max(height - 1, 1)))
    return image


def _generate_demo_image(
    *,
    practice_name: str,
    treatment: str,
    tagline: str,
    theme: DemoTheme,
    variant: str,
    seed: int,
) -> bytes:
    width, height = 1600, 1200
    randomizer = random.Random(seed)
    top = theme.top if variant == "before" else _lerp_color(theme.top, theme.glow, 0.45)
    bottom = theme.bottom if variant == "before" else _lerp_color(theme.bottom, theme.glow, 0.35)
    base = _gradient_canvas(width, height, top, bottom).convert("RGBA")

    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    blobs = [
        (int(width * 0.2), int(height * 0.22), 420),
        (int(width * 0.82), int(height * 0.24), 360),
        (int(width * 0.58), int(height * 0.82), 460),
    ]
    for center_x, center_y, radius in blobs:
        shift = -20 if variant == "before" else 20
        color = (*theme.glow, 90 if variant == "before" else 120)
        glow_draw.ellipse(
            (
                center_x - radius + shift,
                center_y - radius,
                center_x + radius + shift,
                center_y + radius,
            ),
            fill=color,
        )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=90 if variant == "before" else 70))
    base = Image.alpha_composite(base, glow_layer)

    form_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    form_draw = ImageDraw.Draw(form_layer)
    silhouette = theme.silhouette
    accent = theme.accent

    head_bbox = (
        int(width * 0.62),
        int(height * 0.18),
        int(width * 0.9),
        int(height * 0.56),
    )
    if variant == "after":
        head_bbox = (
            head_bbox[0] + 10,
            head_bbox[1] - 8,
            head_bbox[2] - 12,
            head_bbox[3] - 14,
        )

    form_draw.ellipse(head_bbox, fill=(*silhouette, 238))
    shoulder_box = (
        int(width * 0.46),
        int(height * 0.48),
        int(width * 0.96),
        int(height * 0.96),
    )
    form_draw.rounded_rectangle(shoulder_box, radius=220, fill=(*_lerp_color(silhouette, theme.bottom, 0.4), 228))

    contour_points = [
        (int(width * 0.74), int(height * 0.22)),
        (int(width * 0.83), int(height * 0.29)),
        (int(width * 0.84), int(height * 0.41)),
        (int(width * 0.79), int(height * 0.5)),
        (int(width * 0.73), int(height * 0.58)),
        (int(width * 0.7), int(height * 0.66)),
    ]
    if variant == "after":
        contour_points = [
            (x + randomizer.randint(-6, 8), y + randomizer.randint(-6, 6))
            for x, y in contour_points
        ]
    form_draw.line(contour_points, fill=(*accent, 210), width=10, joint="curve")
    form_draw.arc(
        (int(width * 0.58), int(height * 0.14), int(width * 0.94), int(height * 0.62)),
        start=258,
        end=50,
        fill=(*accent, 170),
        width=4,
    )

    if variant == "before":
        form_draw.ellipse(
            (int(width * 0.67), int(height * 0.33), int(width * 0.83), int(height * 0.41)),
            fill=(0, 0, 0, 18),
        )
    else:
        form_draw.arc(
            (int(width * 0.66), int(height * 0.27), int(width * 0.88), int(height * 0.44)),
            start=205,
            end=334,
            fill=(*theme.glow, 190),
            width=8,
        )

    form_layer = form_layer.filter(ImageFilter.GaussianBlur(radius=1))
    base = Image.alpha_composite(base, form_layer)

    frame = ImageDraw.Draw(base)
    margin = 54
    frame.rounded_rectangle(
        (margin, margin, width - margin, height - margin),
        radius=44,
        outline=(255, 255, 255, 120),
        width=2,
    )

    label_font = _load_font(24)
    title_font = _load_font(48)
    copy_font = _load_font(26)
    meta_font = _load_font(20)

    frame.rounded_rectangle(
        (82, 86, 290, 134),
        radius=24,
        fill=(255, 255, 255, 182),
    )
    frame.text((106, 100), DEMO_TAG, fill=accent, font=label_font)
    frame.text((84, height - 240), treatment, fill=(34, 31, 31), font=title_font)
    frame.text((86, height - 184), tagline, fill=(66, 59, 58), font=copy_font)
    frame.text(
        (86, height - 132),
        f"{practice_name} • {'Concept before' if variant == 'before' else 'Concept after'}",
        fill=(82, 77, 76),
        font=meta_font,
    )
    frame.text(
        (width - 270, height - 130),
        "Illustrative placeholder",
        fill=(82, 77, 76),
        font=meta_font,
    )

    output = BytesIO()
    base.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def _store_session_image(
    *,
    session: Session,
    image_kind: str,
    image_bytes: bytes,
) -> tuple[str, str, int, int]:
    storage = get_storage()
    compressed, width, height = compress_for_web(image_bytes)
    filename = f"{image_kind}.jpg"
    original_key = f"{session.practice_id}/sessions/{session.id}/{image_kind}/original.jpg"
    web_key = f"{session.practice_id}/sessions/{session.id}/{image_kind}/web.jpg"
    storage.save_bytes(original_key, image_bytes)
    storage.save_bytes(web_key, compressed)
    return original_key, web_key, width, height


def _seed_session(
    *,
    db: OrmSession,
    practice: Practice,
    spec: DemoPracticeSpec,
    session_spec: DemoSessionSpec,
    session_index: int,
) -> Session:
    now = utcnow()
    created_at = now - timedelta(days=(session_index + 2) * 10)
    captured_at = created_at + timedelta(days=1)
    after_captured_at = created_at + timedelta(days=7)
    published_at = created_at + timedelta(days=8)

    session = Session(
        practice_id=practice.id,
        patient_initials=session_spec.patient_initials,
        treatment=session_spec.treatment,
        category=session_spec.category,
        status=SessionStatus.published.value if session_spec.published else SessionStatus.pending_after.value,
        obscure_mode=session_spec.obscure_mode,
        treatment_details=session_spec.treatment_details,
        consent_tier=session_spec.consent_tier if session_spec.published else None,
        consent_at=after_captured_at if session_spec.published else None,
        discount_applied=session_spec.credit.amount if session_spec.credit else 0,
        captured_at=captured_at,
        signed_at=captured_at,
        after_captured_at=after_captured_at if session_spec.published else None,
        after_provenance="Seeded demo upload" if session_spec.published else None,
        page_views=session_spec.page_views,
        created_at=created_at,
        updated_at=published_at if session_spec.published else now,
    )
    db.add(session)
    db.flush()

    if session_spec.before_asset:
        before_bytes = (SEED_ASSETS_DIR / session_spec.before_asset).read_bytes()
    else:
        before_bytes = _generate_demo_image(
            practice_name=spec.name,
            treatment=session_spec.treatment,
            tagline=session_spec.tagline,
            theme=spec.theme,
            variant="before",
            seed=session_index * 11 + len(spec.name),
        )
    before_original_key, before_web_key, before_width, before_height = _store_session_image(
        session=session,
        image_kind="before",
        image_bytes=before_bytes,
    )
    session.before_original_image_key = before_original_key
    session.before_image_key = before_web_key
    session.before_image_width = before_width
    session.before_image_height = before_height
    session.capture_hash = sha256_hexdigest(before_bytes)
    session.sign_hash = session.capture_hash

    if session_spec.published:
        if session_spec.after_asset:
            after_bytes = (SEED_ASSETS_DIR / session_spec.after_asset).read_bytes()
        else:
            after_bytes = _generate_demo_image(
                practice_name=spec.name,
                treatment=session_spec.treatment,
                tagline=session_spec.tagline,
                theme=spec.theme,
                variant="after",
                seed=session_index * 17 + len(spec.slug),
            )
        after_original_key, after_web_key, after_width, after_height = _store_session_image(
            session=session,
            image_kind="after",
            image_bytes=after_bytes,
        )
        session.after_original_image_key = after_original_key
        session.after_image_key = after_web_key
        session.after_image_width = after_width
        session.after_image_height = after_height
        session.after_capture_hash = sha256_hexdigest(after_bytes)
        session.published_at = published_at
        session.published_destinations = ["widget", "gallery"]
        session.publish_hash = build_publish_hash(session, published_at)
    else:
        session.after_capture_hash = None

    return session


def seed_demo_dataset(*, reset_first: bool = False) -> dict:
    with SessionLocal() as db:
        if reset_first:
            delete_synthetic_records(db)

        created_practices = 0
        created_sessions = 0
        created_credits = 0

        for spec in DEMO_PRACTICES:
            practice = Practice(
                name=spec.name,
                location=spec.location,
                website=normalize_website(spec.website),
                widget_slug=spec.slug,
                default_discount_full=150,
                default_discount_partial=75,
                default_discount_blur=25,
                credit_expiration_days=180,
                auto_publish=False,
            )
            db.add(practice)
            db.flush()

            user = User(
                email=spec.owner_email.lower(),
                password_hash=hash_password(DEMO_PASSWORD),
                name=spec.owner_name,
                initials=derive_initials(spec.owner_name),
                role=Role.owner.value,
                practice_id=practice.id,
            )
            db.add(user)
            db.flush()

            practice.owner_id = user.id
            created_practices += 1

            for session_index, session_spec in enumerate(spec.sessions, start=1):
                session = _seed_session(
                    db=db,
                    practice=practice,
                    spec=spec,
                    session_spec=session_spec,
                    session_index=session_index,
                )
                created_sessions += 1

                if session_spec.credit and session_spec.published:
                    earned_at = session.published_at or utcnow()
                    credit = Credit(
                        practice_id=practice.id,
                        session_id=session.id,
                        followup_id=None,
                        patient_initials=session.patient_initials,
                        patient_email=f"{session.patient_initials.lower()}@{DEMO_EMAIL_DOMAIN}",
                        code=f"VERIBA-{DEMO_EMAIL_SUFFIXES[spec.slug].upper()}-{session_index:02d}",
                        amount=session_spec.credit.amount,
                        description=f"${session_spec.credit.amount} off your next visit",
                        consent_tier=session_spec.consent_tier,
                        status=session_spec.credit.status,
                        earned_at=earned_at,
                        expires_at=earned_at + timedelta(days=session_spec.credit.days_until_expiry),
                        redeemed_at=(
                            earned_at + timedelta(days=12)
                            if session_spec.credit.status == CreditStatus.redeemed.value
                            else None
                        ),
                        redeemed_by=session_spec.credit.redeemed_by,
                        void_reason=session_spec.credit.void_reason,
                    )
                    db.add(credit)
                    created_credits += 1

        db.commit()

        return {
            "practices": created_practices,
            "sessions": created_sessions,
            "credits": created_credits,
            "demo_password": DEMO_PASSWORD,
            "accounts": [
                {
                    "practice": spec.name,
                    "email": spec.owner_email,
                    "password": DEMO_PASSWORD,
                    "slug": spec.slug,
                }
                for spec in DEMO_PRACTICES
            ],
        }


def reset_demo_dataset() -> dict:
    with SessionLocal() as db:
        return delete_synthetic_records(db)
