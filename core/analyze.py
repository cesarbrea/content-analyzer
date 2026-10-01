"""Orchestrates analysis of one image: K tagging runs -> merge -> certainty scores."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from core.brief import evaluate_alignment
from core.config import MODEL, cost_usd
from core.images import prepare_image
from core.merge import merge_tags, normalize
from core.scoring import Observation, score_tags
from core.tagger import tag_image


def analyze_image(data: bytes, filename: str, k: int, brief: str = "",
                  on_progress: Callable[[str], None] | None = None) -> dict:
    """If brief is non-empty, alignment is evaluated too.
    on_progress is called from the calling thread (safe for Streamlit)."""
    say = on_progress or (lambda msg: None)
    jpeg = prepare_image(data)
    usage = {"input_tokens": 0, "output_tokens": 0}

    say(f"Tagging: 0/{k} runs done")
    runs: dict[int, object] = {}
    with ThreadPoolExecutor(max_workers=k) as pool:
        futures = {pool.submit(tag_image, jpeg, i, filename): i for i in range(k)}
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
        alignment, u = evaluate_alignment(jpeg, runs[0].caption, scores, brief, filename)
        _add(usage, u)

    return {
        "filename": filename,
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
        "image_jpeg": jpeg,
    }


def _add(total: dict, u: dict) -> None:
    total["input_tokens"] += u["input_tokens"]
    total["output_tokens"] += u["output_tokens"]
