"""Image normalization before sending to Claude."""
import io

from PIL import Image, ImageOps

from core.config import MAX_IMAGE_EDGE


def prepare_image(data: bytes, max_edge: int = MAX_IMAGE_EDGE) -> bytes:
    """Fix EXIF orientation, convert to RGB, shrink so the long edge <= max_edge. Returns JPEG bytes."""
    img = Image.open(io.BytesIO(data))
    img.seek(0)  # first frame for animated GIFs
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()
