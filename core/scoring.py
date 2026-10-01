"""Certainty computation and filtering. Pure functions, no API calls."""
from dataclasses import dataclass, asdict

from core.config import W_AGREEMENT, W_CONFIDENCE


@dataclass
class Observation:
    run_index: int
    raw_tag: str
    canonical_tag: str
    source: str
    self_confidence: int  # 0-100
    evidence: str


@dataclass
class TagScore:
    tag: str
    source: str
    agreement: float             # 0-1, share of runs that produced the tag
    mean_self_confidence: float  # 0-1
    certainty: float             # 0-1
    runs_seen: int
    evidence: str

    def to_dict(self):
        return asdict(self)


def score_tags(observations: list[Observation], k: int,
               w_agreement: float = W_AGREEMENT, w_confidence: float = W_CONFIDENCE) -> list[TagScore]:
    """Combine K runs into one certainty score per canonical tag, sorted high to low."""
    by_tag: dict[str, list[Observation]] = {}
    for o in observations:
        by_tag.setdefault(o.canonical_tag, []).append(o)

    scores = []
    for tag, obs in by_tag.items():
        # A tag can appear twice in one run after merging; keep the most confident per run.
        best_per_run: dict[int, Observation] = {}
        for o in obs:
            if o.run_index not in best_per_run or o.self_confidence > best_per_run[o.run_index].self_confidence:
                best_per_run[o.run_index] = o
        per_run = list(best_per_run.values())

        agreement = len(per_run) / k
        mean_conf = sum(o.self_confidence for o in per_run) / len(per_run) / 100
        if k == 1:
            certainty = mean_conf
        else:
            certainty = w_agreement * agreement + w_confidence * mean_conf
        top = max(per_run, key=lambda o: o.self_confidence)
        scores.append(TagScore(tag, top.source, agreement, mean_conf, certainty, len(per_run), top.evidence))

    scores.sort(key=lambda s: (-s.certainty, s.tag))
    return scores


def filter_tags(scores: list[TagScore], mode: str, value: float) -> list[TagScore]:
    """mode 'top_n': keep the first `value` tags. mode 'threshold': keep certainty >= value (percent)."""
    if mode == "top_n":
        return scores[: int(value)]
    if mode == "threshold":
        return [s for s in scores if s.certainty * 100 >= value]
    raise ValueError(f"unknown mode: {mode}")
