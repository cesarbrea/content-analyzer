"""Orchestrates analysis of one asset (image or video):
prep -> K tagging runs -> merge -> certainty scores -> optional brief alignment."""
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from core import video
from core.brief import evaluate_alignment
from core.config import MODEL, VIDEO_FRAME_EDGE, VIDEO_TYPES, cost_usd
from core.images import prepare_image
from core.merge import merge_tags, normalize
from core.scoring import Observation, score_tags
from core.tagger import media_blocks, tag_asset


def asset_kind(filename: str) -> str:
    return "video" if Path(filename).suffix.lower().lstrip(".") in VIDEO_TYPES else "image"


def analyze_asset(data: bytes, filename: str, k: int, brief: str = "",
                  on_progress: Callable[[str], None] | None = None) -> dict:
    """If brief is non-empty, alignment is evaluated too.
    on_progress is called from the calling thread (safe for Streamlit)."""
    say = on_progress or (lambda msg: None)
    kind = asset_kind(filename)
    usage = {"input_tokens": 0, "output_tokens": 0}

    if kind == "image":
        frames = [(None, prepare_image(data))]
        transcript, meta = None, {}
    else:
        frames, transcript, meta = _prepare_video(data, filename, say)
    blocks = media_blocks(frames, transcript, meta.get("has_audio", False))

    say(f"Tagging: 0/{k} runs done")
    runs: dict[int, object] = {}
    with ThreadPoolExecutor(max_workers=k) as pool:
        futures = {pool.submit(tag_asset, blocks, kind, i, filename): i for i in range(k)}
        for fut in as_completed(futures):
            result, u = fut.result()
            runs[futures[fut]] = result
            _add(usage, u)
            say(f"Tagging: {len(runs)}/{k} runs done")

    say("Merging synonymous tags across runs")
    raw = [(i, t) for i in sorted(runs) for t in runs[i].tags]
    mapping, u = merge_tags([normalize(t.tag) for _, t in raw], filename)
    _add(usage, u)

    observations = [
        Observation(
            run_index=i,
            raw_tag=t.tag,
            canonical_tag=mapping[normalize(t.tag)],
            source=t.source,
            self_confidence=max(0, min(100, t.self_confidence)),
            evidence=t.evidence,
        )
        for i, t in raw
    ]
    scores = score_tags(observations, k)

    alignment = None
    if brief.strip():
        say("Evaluating against the creative brief")
        alignment, u = evaluate_alignment(blocks, runs[0].caption, scores, brief, filename)
        _add(usage, u)

    return {
        "filename": filename,
        "kind": kind,
        "model": MODEL,
        "k": k,
        "caption": runs[0].caption,
        "captions": [runs[i].caption for i in sorted(runs)],
        "scores": scores,
        "observations": observations,
        "merge_map": {a: b for a, b in sorted(mapping.items()) if a != b},
        "alignment": alignment,
        "usage": usage,
        "cost_usd": cost_usd(MODEL, usage["input_tokens"], usage["output_tokens"]),
        "frames": frames,                 # [(timestamp or None, jpeg)]
        "transcript": transcript,         # {language, segments} or None
        "video_meta": meta,               # {duration, width, height, has_audio} for videos
        "image_jpeg": frames[0][1],       # thumbnail / display image
        "video_bytes": data if kind == "video" else None,
    }


def blocks_for(result: dict) -> list[dict]:
    """Rebuild the content blocks for a stored result (used to re-evaluate alignment)."""
    return media_blocks(result["frames"], result["transcript"], result["video_meta"].get("has_audio", False))


def _prepare_video(data: bytes, filename: str, say) -> tuple[list, dict | None, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"input{Path(filename).suffix.lower()}"
        path.write_bytes(data)
        meta = video.probe(path)

        say("Finding scene changes")
        times = video.pick_timestamps(meta["duration"], video.scene_changes(path))
        say(f"Extracting {len(times)} frames")
        frames = [(t, prepare_image(video.extract_frame(path, t), VIDEO_FRAME_EDGE)) for t in times]

        transcript = None
        if meta["has_audio"]:
            say("Transcribing speech (on this laptop)")
            wav = Path(tmp) / "audio.wav"
            video.extract_audio(path, wav)
            from core.audio import transcribe
            transcript = transcribe(wav)
    return frames, transcript, meta


def _add(total: dict, u: dict) -> None:
    total["input_tokens"] += u["input_tokens"]
    total["output_tokens"] += u["output_tokens"]


# Kept for scripts and tests written against the image-only version.
analyze_image = analyze_asset
