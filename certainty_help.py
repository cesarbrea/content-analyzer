"""Content for the 'How certainty works' tab. Numbers are read live from config and scoring."""
import streamlit as st

from core import config
from core.brief import DIMENSIONS
from core.scoring import Observation, score_tags
from core.tagger import CONFIDENCE_BANDS


def _example(k: int, runs_seen: int, conf: int) -> float:
    obs = [Observation(i, "t", "t", "visual", conf, "") for i in range(runs_seen)]
    return score_tags(obs, k)[0].certainty


def render_certainty_help(k: int) -> None:
    wa, wc = config.W_AGREEMENT, config.W_CONFIDENCE
    kk = max(k, 3)  # worked example needs several runs

    st.header("How certainty works")
    st.markdown(f"""
Each tag's **certainty** estimates how likely it is that the tag accurately describes the asset.
Claude doesn't report a true probability for its answers, so the app builds the score from two
signals you can inspect: **agreement** and **self-confidence**.

### 1. Agreement: does the tag keep coming back?
The asset is analyzed **K times** independently (currently **K = {k}**, set in the sidebar).
Each run produces its own list of tags. Wording varies between runs ("sailboat" in one, "sailing boat"
in another), so the app first **merges variants that mean the same thing** under one tag. The
**Merged variants** section under each result shows what was merged.

**Agreement** is the share of runs that produced the tag. A tag found in all {kk} of {kk} runs has
100% agreement; one found in only 1 of {kk} has {1/kk:.0%}. Tags that are clearly present tend to
come back every time. Borderline or speculative ones come and go.

### 2. Self-confidence: how sure is Claude in each run?
In every run, Claude also rates each tag it produces from **0 to 100**, answering the question
*"how sure am I that this tag accurately describes this asset?"* It uses this rubric, which is part
of its instructions:
""")
    st.table({"Rating": [r for r, _ in CONFIDENCE_BANDS], "Meaning": [m for _, m in CONFIDENCE_BANDS]})
    st.markdown(f"""
Claude is also told to be calibrated and not to default to high numbers.

The app averages this rating over the runs in which the tag appeared, giving **self-confidence** as a
percentage. Self-confidence captures *how clearly* something is present: a large sailboat in the
foreground rates higher than a distant speck that might be a boat. Agreement captures *how
reliably* Claude notices it.

### 3. Combining the two
> **certainty = {wa:.0%} × agreement + {wc:.0%} × self-confidence**

Agreement gets more weight because it's measured directly, while self-confidence is Claude's own
judgment. With **K = 1** there's nothing to agree across, so certainty equals self-confidence
alone and should be treated as uncalibrated.

**Worked examples (K = {kk}):**

| Tag appears in | Avg. self-confidence | Certainty |
|---|---|---|
| {kk} of {kk} runs | 95 | **{_example(kk, kk, 95):.0%}** ({wa:.0%}×100% + {wc:.0%}×95%) |
| {kk} of {kk} runs | 60 | **{_example(kk, kk, 60):.0%}** (always noticed, but ambiguous) |
| 1 of {kk} runs | 90 | **{_example(kk, 1, 90):.0%}** (confident once, but not reproduced) |
| 1 of {kk} runs | 40 | **{_example(kk, 1, 40):.0%}** (speculative) |

Hover over any bar in the tag chart to see its agreement, self-confidence, number of runs, and the
evidence Claude gave.

### What the score does and doesn't mean
- **Use it to rank and filter** tags, e.g. *show only tags above 70%*. A higher score means a more
  reliable tag.
- **It isn't a calibrated probability.** An 80% tag isn't guaranteed to be right 80% of the time.
  Language models often lean confident, and the runs share the same model and image, so they aren't
  fully independent.
- **More runs, steadier scores, higher cost.** Each extra run adds about ${config.EST_COST_PER_RUN:.3f} per image.
  K = 3 is a reasonable balance. K = 5 separates borderline tags more sharply.
- A planned improvement is to check scores against a small hand-labelled set of images, to measure
  how well they match reality.

---

## How brief alignment is scored
When a creative brief is provided, Claude evaluates the asset (the image, plus its caption and tags
as hints) on four fixed dimensions:
""")
    st.table({"Dimension": [d.capitalize() for d in DIMENSIONS], "Question": list(DIMENSIONS.values())})
    st.markdown("""
Each dimension is scored from **−1 to +1**:

| Score | Meaning |
|---|---|
| +1 | fully conforms to the brief |
| +0.5 | mostly conforms, with clear gaps |
| 0 | absent, not addressed, or neutral |
| −0.5 | partly works against the brief |
| −1 | directly contradicts the brief |

**Absence scores 0, not negative.** If an asset simply doesn't show something the brief calls for
(for example, no people or no product), that dimension scores 0 and the rationale says what's
missing. Negative scores are reserved for content that *is* present and works against the brief:
young models when the brief targets older sailors, a cartoon treatment when it calls for realism,
or a conflicting setting.

The **overall alignment** is the simple average of the four. Each score comes with a one-sentence
rationale, and Claude adds 3–5 specific suggestions for bringing the asset closer to the brief.
Alignment is a single judgment by Claude (not repeated runs), so treat small differences
(e.g. +0.6 vs +0.7) as noise.
""")
