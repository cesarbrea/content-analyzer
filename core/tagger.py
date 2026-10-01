"""Caption + emergent tag extraction for one image (one run)."""
import base64
from typing import Literal

from pydantic import BaseModel

from core.config import EFFORT_TAGGING, MAX_TAGS_REQUESTED
from core.llm import parse_call


class Tag(BaseModel):
    tag: str
    source: Literal["visual", "speech", "sound"]
    self_confidence: int
    evidence: str


class TaggingResult(BaseModel):
    caption: str
    tags: list[Tag]


# Rubric Claude uses for self_confidence. Also shown on the "How certainty works" tab.
CONFIDENCE_BANDS = [
    ("90-100", "clearly and centrally present; any viewer would agree."),
    ("70-89", "clearly present but small, partial, or secondary."),
    ("40-69", "plausible but ambiguous (distance, blur, occlusion, interpretation)."),
    ("0-39", "speculative; include only if it would matter for advertising review."),
]
_BANDS_TEXT = "\n".join(f"- {r}: {m}" for r, m in CONFIDENCE_BANDS)

SYSTEM = f"""You analyze advertising creative assets and describe what they contain.

Return:
1. caption: one or two plain sentences describing the asset, so a reviewer can check what you see.
2. tags: up to {MAX_TAGS_REQUESTED} descriptive tags.

Tag rules:
- Each tag is one or two words, lowercase, singular where natural (e.g. "sailboat", "open water", "warm light").
- Choose the words yourself; there is no fixed vocabulary.
- Cover what is actually present: subjects, people and their apparent age group or gender presentation, activity, setting, time of day, weather, notable objects, clothing and product details, colors, composition, visual style (photo, illustration, 3D render...), and mood.
- Prefer concrete, observable tags over interpretation. Describe demographics only as apparent, never as identity.
- No duplicates or near-duplicates within your list.
- source: "visual" for anything seen in the image.
- evidence: a few words saying where or how it appears (e.g. "foreground, left", "sail color", "overall palette").

self_confidence (0-100) is how sure you are that the tag accurately describes the asset:
{_BANDS_TEXT}
Be calibrated: do not default to high numbers."""


def tag_image(jpeg_bytes: bytes, run_index: int, filename: str = "") -> tuple[TaggingResult, dict]:
    b64 = base64.standard_b64encode(jpeg_bytes).decode("utf-8")
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": "Caption and tag this image."},
        ],
    }]
    return parse_call("tag_image", TaggingResult, messages, SYSTEM, EFFORT_TAGGING,
                      meta={"file": filename, "run_index": run_index})
