"""Creative brief: drafting from a product description, and asset alignment scoring."""
from pydantic import BaseModel

from core.config import EFFORT_ALIGNMENT, EFFORT_BRIEF_DRAFT
from core.llm import parse_call, text_call
from core.scoring import TagScore

# Fixed alignment dimensions (from the earlier variant). Order is display order.
DIMENSIONS = {
    "customer": "Does the asset show or speak to the target audience described in the brief?",
    "context": "Is the environment / setting consistent with the brief?",
    "product": "Is the product represented well, including its key features and benefits?",
    "style": "Does the visual treatment fit (realist vs illustrated/abstract, tone, brand feel)?",
}

# ---------------------------------------------------------------- drafting

BRIEF_SECTIONS = ["Objective", "Target audience", "Product & key benefits", "Single-minded proposition",
                  "Tone & style", "Setting / context", "Mandatories", "Success measures"]

DRAFT_SYSTEM = f"""You are a senior advertising strategist. Turn the user's product description into a
concise creative brief of 150-250 words. Never exceed 250 words in total; keep each section to
one to three short sentences.

Use exactly these section headings, in this order, each on its own line followed by a colon:
{chr(10).join(BRIEF_SECTIONS)}

Be specific and concrete. Where the description leaves something out, make a sensible, clearly
plausible assumption rather than leaving the section empty. Plain text only: no markdown symbols,
no preamble, no closing remarks."""


def draft_brief(product_description: str) -> tuple[str, dict]:
    messages = [{"role": "user", "content": f"Product description:\n{product_description.strip()}"}]
    return text_call("draft_brief", messages, DRAFT_SYSTEM, EFFORT_BRIEF_DRAFT)


# ---------------------------------------------------------------- alignment

class DimensionScore(BaseModel):
    score: float      # -1 .. +1
    rationale: str


class AlignmentResult(BaseModel):
    customer: DimensionScore
    context: DimensionScore
    product: DimensionScore
    style: DimensionScore
    suggestions: list[str]


ALIGN_SYSTEM = f"""You evaluate how well an advertising creative asset conforms to a creative brief.

Score each dimension on a scale from -1 to +1:
  +1   fully conforms to the brief
  +0.5 mostly conforms, with clear gaps
   0   absent / not addressed / neutral
  -0.5 partly works against the brief
  -1   directly contradicts the brief

Absence is 0, not negative, on every dimension including product: if the asset simply doesn't show
something the brief calls for (e.g. no people, no product at all), score that dimension exactly 0 and
say what is missing in the rationale. "Missing" alone never justifies a negative score. Reserve negative
scores for content that is present and works against the brief (e.g. young models when the brief
targets older sailors, a cartoon treatment when the brief calls for realism, a setting that conflicts
with the brief).

Dimensions:
{chr(10).join(f"- {k}: {v}" for k, v in DIMENSIONS.items())}

For each dimension give a one-sentence rationale that points to what is (or is not) in the asset.
Then give 3-5 specific, actionable suggestions for changing the asset to conform more closely to the
brief (e.g. what to show, from how close, which feature or benefit to make visible). Suggestions
should be things a creative team could act on, not generic advice.

You are given the asset (an image, or a video as timestamped frames plus a speech transcript) and
machine-extracted tags with certainty scores. Use the tags as hints, but trust the asset itself where
they disagree. For a video, judge the video as a whole, including what is said, and point suggestions
at specific moments where useful (e.g. "at 0:08, show the fabric up close")."""


def evaluate_alignment(blocks: list[dict], caption: str, scores: list[TagScore], brief: str,
                       filename: str = "") -> tuple[dict, dict]:
    """blocks: the asset's content blocks from tagger.media_blocks (image, or video frames + transcript).
    Returns ({dimensions: {name: {score, rationale}}, overall, suggestions, brief}, usage)."""
    tag_lines = "\n".join(f"- {s.tag} ({s.certainty:.0%})" for s in scores[:30])
    messages = [{
        "role": "user",
        "content": blocks + [
            {"type": "text", "text": (
                f"<brief>\n{brief.strip()}\n</brief>\n\n"
                f"<caption>{caption}</caption>\n\n"
                f"<tags>\n{tag_lines}\n</tags>\n\n"
                "Evaluate this asset against the brief."
            )},
        ],
    }]
    result, usage = parse_call("evaluate_alignment", AlignmentResult, messages, ALIGN_SYSTEM,
                               EFFORT_ALIGNMENT, meta={"file": filename})
    dims = {}
    for name in DIMENSIONS:
        d = getattr(result, name)
        dims[name] = {"score": max(-1.0, min(1.0, d.score)), "rationale": d.rationale}
    overall = sum(d["score"] for d in dims.values()) / len(dims)
    return {"dimensions": dims, "overall": overall, "suggestions": result.suggestions, "brief": brief}, usage
