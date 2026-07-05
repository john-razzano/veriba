from io import BytesIO

import cairosvg
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

from app.core.config import get_settings
from app.core.security import sha256_hexdigest


async def read_upload_bytes(file: UploadFile) -> bytes:
    settings = get_settings()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds 10MB limit")
    return data


def compress_for_web(data: bytes) -> tuple[bytes, int, int]:
    settings = get_settings()
    try:
        image = Image.open(BytesIO(data))
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported image format") from exc

    image = image.convert("RGB")
    width, height = image.size
    if width > settings.max_web_width:
        ratio = settings.max_web_width / width
        image = image.resize((settings.max_web_width, int(height * ratio)))
        width, height = image.size

    quality = 80
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality, optimize=True)
    while output.tell() > settings.max_web_bytes and quality > 45:
        quality -= 5
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)

    return output.getvalue(), width, height


def image_hash(data: bytes) -> str:
    return sha256_hexdigest(data)


def compute_blurhash(image_bytes: bytes, components_x: int = 4, components_y: int = 3) -> str | None:
    """Encode a blurhash from image bytes. Resizes to ≤32px first for performance."""
    try:
        import blurhash as _bh
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        max_dim = 32
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        # blurhash expects a 3-D list[y][x][r,g,b]; PIL Image doesn't implement __len__
        pixel_array = [[list(img.getpixel((x, y))) for x in range(img.width)] for y in range(img.height)]
        return _bh.encode(pixel_array, components_x=components_x, components_y=components_y)
    except Exception:
        return None


def render_signature_png(signature_svg: str) -> bytes:
    svg_markup = signature_svg.strip()
    if not svg_markup.startswith("<svg"):
        svg_markup = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="120" '
            'viewBox="0 0 320 120">'
            f'<path d="{signature_svg}" fill="none" stroke="black" stroke-width="4" />'
            "</svg>"
        )
    return cairosvg.svg2png(bytestring=svg_markup.encode("utf-8"))

