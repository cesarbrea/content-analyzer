"""Orchestrates analysis of one asset (image or video):
prep -> K tagging runs -> merge -> certainty scores -> optional brief alignment."""
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from core import video
from core.brief import evaluate_alignment
from core.config import (MODEL, STORY_FRAME_EDGE, STORY_MAX_FRAMES, STORY_MIN_FRAMES, STORY_SECONDS_PER_FRAME,
                         VIDEO_FRAME_EDGE, VIDEO_TYPES, cost_usd)
from core.images import prepare_image
from core.merge import merge_tags, normalize
from core.narrative import read_story
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
        transcript, meta, story_frames = None, {}, []
    else:
        frames, transcript, meta, story_frames = _prepare_video(data, filename, say)
    blocks = media_blocks(frames, transcript, meta.get("has_audio", False))

    say(f"Tagging: 0/{k} runs done")
    runs: dict[int, object] = {}
    story, story_error = None, None
    with ThreadPoolExecutor(max_workers=k + 1) as pool:
        futures = {pool.submit(tag_asset, blocks, kind, i, filename): i for i in range(k)}
        # The story reading runs alongside tagging; a failure there doesn't sink the rest of the analysis.
        story_future = (pool.submit(read_story, story_frames, transcript, meta.get("has_audio", False), brief, filename)
                        if kind == "video" and story_frames else None)
        for fut in as_completed(futures):
            result, u = fut.result()
            runs[futures[fut]] = result
            _add(usage, u)
            say(f"Tagging: {len(runs)}/{k} runs done")
        if story_future:
            say(f"Reading the story ({len(story_frames)} frames)")
            try:
                story, u = story_future.result()
                _add(usage, u)
            except Exception as e:
                story_error = f"{type(e).__name__}: {e}"

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
        "story": story,                   # {logline, beats, characters, arc, gaps, scores?, suggestions?} or None
        "story_error": story_error,
        "story_frames": story_frames,     # [(timestamp, small jpeg)] for re-scoring against a new brief
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


def _prepare_video(data: bytes, filename: str, say) -> tuple[list, dict | None, dict, list]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"input{Path(filename).suffix.lower()}"
        path.write_bytes(data)
        meta = video.probe(path)

        say("Finding scene changes")
        scenes = video.scene_changes(path)
        times = video.pick_timestamps(meta["duration"], scenes)
        story_times = video.pick_timestamps(meta["duration"], scenes, STORY_SECONDS_PER_FRAME,
                                            STORY_MIN_FRAMES, STORY_MAX_FRAMES)
        say(f"Extracting {len(times)} frames for tagging and {len(story_times)} smaller frames for the story")
        with ThreadPoolExecutor(max_workers=6) as pool:
            full = list(pool.map(lambda t: video.extract_frame(path, t), sorted(set(times) | set(story_times))))
        raw = dict(zip(sorted(set(times) | set(story_times)), full))
        frames = [(t, prepare_image(raw[t], VIDEO_FRAME_EDGE)) for t in times]
        story_frames = [(t, prepare_image(raw[t], STORY_FRAME_EDGE)) for t in story_times]

        transcript = None
        if meta["has_audio"]:
            say("Transcribing speech (on this laptop)")
            wav = Path(tmp) / "audio.wav"
            video.extract_audio(path, wav)
            from core.audio import transcribe
            transcript = transcribe(wav)
    return frames, transcript, meta, story_frames


def _add(total: dict, u: dict) -> None:
    total["input_tokens"] += u["input_tokens"]
    total["output_tokens"] += u["output_tokens"]


# Kept for scripts and tests written against the image-only version.
analyze_image = analyze_asset
