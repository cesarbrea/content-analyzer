"""Settings and defaults. Values can be overridden in .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
LOG_DIR = DATA_DIR / "logs"

MODEL = os.getenv("CA_MODEL", "claude-sonnet-5")

# USD per 1M tokens, for cost estimates. Thinking tokens are billed as output.
PRICES = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

EFFORT_TAGGING = "low"
EFFORT_MERGE = "low"
EFFORT_ALIGNMENT = "medium"
EFFORT_BRIEF_DRAFT = "medium"

DEFAULT_K = 3              # independent tagging runs per asset
MAX_TAGS_REQUESTED = 25    # tags asked for per run (before filtering)
MAX_IMAGE_EDGE = 1568      # px, long edge sent to Claude

# Video: frames sampled at scene changes plus even fill-ins.
VIDEO_TYPES = ["mp4"]
VIDEO_MIN_FRAMES = 4
VIDEO_MAX_FRAMES = 10
VIDEO_SECONDS_PER_FRAME = 2.0   # target density before the min/max caps
VIDEO_SCENE_THRESHOLD = 0.3     # ffmpeg scene score (0-1) that counts as a cut
VIDEO_FRAME_EDGE = 1024         # px, smaller than single images to keep token cost down
WHISPER_MODEL = "base"          # faster-whisper model size; downloads once (~150 MB)

# certainty = W_AGREEMENT * agreement + W_CONFIDENCE * mean_self_confidence
W_AGREEMENT = 0.6
W_CONFIDENCE = 0.4

DEFAULT_TOP_N = 10
DEFAULT_THRESHOLD = 50     # percent


# Per-image cost estimates on Sonnet 5 (measured 2026-09-29/30 on a sample image).
EST_COST_PER_RUN = 0.016
EST_COST_MERGE = 0.004
EST_COST_ALIGNMENT = 0.012
# Video (~9-10 frames at 1024 px, short transcript), measured 2026-10-05 on one short video.
EST_COST_VIDEO_RUN = 0.029
EST_COST_VIDEO_MERGE = 0.011
EST_COST_VIDEO_ALIGNMENT = 0.023


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICES.get(model)
    if p is None:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
