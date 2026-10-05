"""Caption + emergent tag extraction for one asset (one run). An asset is an image, or a video
given as timestamped frames plus an optional speech transcript."""
import base64
from typing import Literal

from pydantic import BaseModel

from core.config import EFFORT_TAGGING, MAX_TAGS_REQUESTED
from core.llm import parse_call
from core.video import fmt_time


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

SYSTEM = f"""You analyze advertising creative assets and describe what they contain. An asset is either a
single image, or a video given as frames sampled at the listed timestamps plus a transcript of its speech.

Return:
1. caption: one or two plain sentences describing the asset (for a video: the video as a whole), so a
   reviewer can check what you see.
2. tags: up to {MAX_TAGS_REQUESTED} descriptive tags.

Tag rules:
- Each tag is one or two words, lowercase, singular where natural (e.g. "sailboat", "open water", "warm light").
- Choose the words yourself; there is no fixed vocabulary.
- Cover what is actually present: subjects, people and their apparent age group or gender presentation, activity, setting, time of day, weather, notable objects, clothing and product details, on-screen text or logos, colors, composition, visual style (photo, illustration, 3D render...), and mood.
- For a video, tag the video as a whole: a tag seen in one frame counts, but rate it lower if it's brief or peripheral. Also tag what is said: topics, claims, product benefits, calls to action, tone of voice.
- Ignore anything that belongs to a video player or screen recording rather than the creative itself (play/pause buttons, progress bars, captions toggles, browser or app chrome).
- Prefer concrete, observable tags over interpretation. Describe demographics only as apparent, never as identity.
- No duplicates or near-duplicates within your list.
- source: "visual" for anything seen; "speech" for anything taken from the transcript.
- evidence: a few words saying where or how it appears (e.g. "foreground, left", "frames 0:03-0:08", "said at 0:12: 'stays cool'").

self_confidence (0-100) is how sure you are that the tag accurately describes the asset:
{_BANDS_TEXT}
Be calibrated: do not default to high numbers. Transcripts are machine-generated and may contain errors."""


def _image_block(jpeg: bytes) -> dict:
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.standard_b64encode(jpeg).decode("utf-8")}}


def media_blocks(frames: list[tuple[float | None, bytes]], transcript: dict | None,
                 has_audio: bool = False) -> list[dict]:
    """Content blocks describing an asset. frames: [(timestamp or None for a still image, jpeg)]."""
    if len(frames) == 1 and frames[0][0] is None:
        return [_image_block(frames[0][1])]
    blocks: list[dict] = []
    for t, jpeg in frames:
        blocks.append({"type": "text", "text": f"Frame at {fmt_time(t)}"})
        blocks.append(_image_block(jpeg))
    if transcript and transcript["segments"]:
        lines = "\n".join(f"[{fmt_time(s['start'])}-{fmt_time(s['end'])}] {s['text']}" for s in transcript["segments"])
        blocks.append({"type": "text", "text": f"<transcript language=\"{transcript['language']}\">\n{lines}\n</transcript>"})
    else:
        blocks.append({"type": "text", "text": "<transcript>" + (
            "No speech detected." if has_audio else "This video has no audio track.") + "</transcript>"})
    return blocks


def tag_asset(blocks: list[dict], kind: str, run_index: int, filename: str = "") -> tuple[TaggingResult, dict]:
    messages = [{"role": "user", "content": blocks + [{"type": "text", "text": f"Caption and tag this {kind}."}]}]
    return parse_call("tag_asset", TaggingResult, messages, SYSTEM, EFFORT_TAGGING,
                      meta={"file": filename, "kind": kind, "run_index": run_index})
