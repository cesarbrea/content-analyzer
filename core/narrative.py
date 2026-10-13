"""Story reading for a video: plot beats over time, characters, and (given a brief) how well the story fits it.
One Claude call over a dense set of small frames plus the transcript."""
from typing import Literal

from pydantic import BaseModel

from core.config import EFFORT_NARRATIVE
from core.llm import parse_call
from core.tagger import media_blocks

NARRATIVE_DIMENSIONS = {
    "plot": "Does the story convey the brief's proposition and key message?",
    "characters": "Do the characters (who they are, how they look and act) fit the target audience, tone and casting in the brief?",
    "structure": "Does the arc work: a hook, a clear middle, an ending or call to action, at a pace that suits the brief?",
    "product_timing": "When and for how long does the product appear, and is it prominent at the right moments (e.g. early, and at the end)?",
}


class Beat(BaseModel):
    start: float      # seconds
    end: float
    summary: str
    evidence: str     # what in the frames or transcript supports it


class Character(BaseModel):
    label: str        # a role, e.g. "host", "shopper in leather jacket"; never a real person's name unless shown on screen
    role: str
    description: str  # apparent age group, gender presentation, clothing, manner
    first_seen: float
    presence: Literal["brief", "recurring", "central"]
    speaks: bool


class Story(BaseModel):
    logline: str
    beats: list[Beat]
    characters: list[Character]
    arc: str          # hook, middle, ending / call to action
    gaps: list[str]   # what could not be determined from the sampled frames and transcript


class NarrativeScore(BaseModel):
    score: float      # -1 .. +1
    rationale: str


class StoryWithBrief(Story):
    plot: NarrativeScore
    characters_fit: NarrativeScore
    structure: NarrativeScore
    product_timing: NarrativeScore
    suggestions: list[str]


SYSTEM = """You read the story of an advertising video from timestamped frames and a speech transcript.
The frames are small, sampled every second or so (more densely at cuts), so you see the video as a sequence.

Return:
- logline: one or two sentences saying what happens.
- beats: the story in order, each with start and end times in seconds (use the frame timestamps and transcript
  times), a one-sentence summary, and evidence (what you saw or heard). Merge frames that show the same moment;
  aim for roughly 4-12 beats.
- characters: each distinct person or character, described by role and apparent appearance (apparent age group,
  gender presentation, clothing, manner). Never identify a real person from their face or voice. Use a name only
  if it appears in on-screen text or is said in the transcript, and then attribute it to that source. Say whether
  they speak. The transcript has no speaker labels, so attribute lines to a character only when context makes it clear.
- arc: the opening hook, the middle, and how it ends (including any call to action).
- gaps: what you could not determine, such as action between sampled frames, music and sound effects (not analyzed),
  small on-screen text, or unclear speakers. Be honest; this is an inference from sampled material.

Transcripts are machine-generated and may contain errors. Ignore video-player or screen-recording chrome."""

BRIEF_SYSTEM = SYSTEM + """

You are also given a creative brief. Score the story against it on four dimensions, each from -1 to +1:
  +1 fully conforms, +0.5 mostly conforms with clear gaps, 0 absent / not addressed / neutral,
  -0.5 partly works against the brief, -1 directly contradicts it.
Absence is 0, not negative: if the story simply doesn't do something the brief calls for, score 0 and say what is
missing. Reserve negative scores for content that is present and works against the brief.
""" + "\n".join(f"- {k}: {v}" for k, v in NARRATIVE_DIMENSIONS.items()) + """
(The scores are fields plot, characters_fit, structure, product_timing.)
Give one sentence of rationale per dimension that points to specific moments. Then give 3-5 actionable suggestions
for changing the story or its timing to fit the brief more closely, citing timestamps where useful
(e.g. "show the product before 0:05")."""


def read_story(frames: list[tuple[float, bytes]], transcript: dict | None, has_audio: bool,
               brief: str = "", filename: str = "") -> tuple[dict, dict]:
    """Returns ({logline, beats, characters, arc, gaps, scores?, suggestions?, brief}, usage).
    scores is {dimension: {score, rationale}} and is present only when a brief is given."""
    if not frames or any(t is None for t, _ in frames):
        raise ValueError("read_story needs timestamped video frames; it does not apply to still images")
    with_brief = bool(brief.strip())
    text = "Read the story of this video."
    if with_brief:
        text = f"<brief>\n{brief.strip()}\n</brief>\n\nRead the story of this video and score it against the brief."
    messages = [{"role": "user", "content": media_blocks(frames, transcript, has_audio) + [{"type": "text", "text": text}]}]
    result, usage = parse_call("read_story", StoryWithBrief if with_brief else Story, messages,
                               BRIEF_SYSTEM if with_brief else SYSTEM, EFFORT_NARRATIVE,
                               meta={"file": filename, "frames": len(frames), "brief": with_brief})
    out = {k: v for k, v in result.model_dump().items()
           if k in ("logline", "beats", "characters", "arc", "gaps")}
    out["brief"] = brief
    if with_brief:
        fields = {"plot": "plot", "characters": "characters_fit", "structure": "structure",
                  "product_timing": "product_timing"}
        out["scores"] = {d: {"score": max(-1.0, min(1.0, getattr(result, f).score)),
                             "rationale": getattr(result, f).rationale} for d, f in fields.items()}
        out["suggestions"] = result.suggestions
    return out, usage
