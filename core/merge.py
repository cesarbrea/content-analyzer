"""Tag normalization and synonym merging across runs."""
import json
import re

from pydantic import BaseModel

from core.config import EFFORT_MERGE
from core.llm import parse_call

def normalize(tag: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Plurals/synonyms are left to merge_tags."""
    t = tag.lower().strip()
    t = re.sub(r"[^\w\s-]", "", t)
    return re.sub(r"[\s_]+", " ", t).strip()


class MergeGroup(BaseModel):
    canonical: str
    variants: list[str]


class MergeResult(BaseModel):
    groups: list[MergeGroup]


SYSTEM = """You merge descriptive image tags that were produced by several independent runs.

Group tags only when they mean the same thing (synonyms, spelling or word-order variants),
e.g. "sailboat" / "sailing boat", "sea" / "ocean", "blue sky" / "clear blue sky".
Do NOT merge a broader tag with a narrower one ("boat" and "sailboat" stay separate),
and do not merge related-but-different ideas ("sunny" and "warm").

For each group, pick the clearest variant from the list as canonical (do not invent new wording).
Every input tag must appear in exactly one group; singletons are their own group."""


def merge_tags(tags: list[str], filename: str = "") -> tuple[dict[str, str], dict]:
    """Return ({tag: canonical}, usage). Tags missing from the model's answer map to themselves."""
    unique = sorted(set(tags))
    if len(unique) <= 1:
        return {t: t for t in unique}, {"input_tokens": 0, "output_tokens": 0}

    messages = [{"role": "user", "content": "Tags:\n" + json.dumps(unique)}]
    result, usage = parse_call("merge_tags", MergeResult, messages, SYSTEM, EFFORT_MERGE,
                               meta={"file": filename, "n_tags": len(unique)})
    mapping: dict[str, str] = {}
    allowed = set(unique)
    for g in result.groups:
        members = [v for v in g.variants if v in allowed]
        if not members:
            continue
        canonical = g.canonical if g.canonical in allowed else members[0]
        for v in members:
            mapping.setdefault(v, canonical)
    for t in unique:
        mapping.setdefault(t, t)
    return mapping, usage
