"""Render the app with canned results (no API calls)."""
import io
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

from core.images import prepare_image
from core.scoring import Observation, score_tags

APP = str(Path(__file__).resolve().parent.parent / "app.py")
BRIEF = "Objective: sell shirts to older sailors."
SUBTITLE = ("This application describes and enhances tags for visual and audio content, and evaluates "
            "this content for conformance with a creative brief on multiple dimensions.")


def _fake_result(with_alignment=False):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (0, 100, 200)).save(buf, format="PNG")
    obs = [Observation(0, "sea", "sea", "visual", 90, "lower half"),
           Observation(1, "sea", "sea", "visual", 80, "lower half"),
           Observation(0, "sun", "sun", "visual", 50, "top right")]
    alignment = None
    if with_alignment:
        dims = {"customer": 0.5, "context": 1.0, "product": -0.5, "style": 0.0}
        alignment = {
            "dimensions": {d: {"score": s, "rationale": f"{d} rationale"} for d, s in dims.items()},
            "overall": sum(dims.values()) / 4,
            "suggestions": ["Show the fabric up close."],
            "brief": BRIEF,
        }
    return {
        "filename": "x.png", "model": "claude-sonnet-5", "k": 2, "caption": "A sea.",
        "captions": ["A sea.", "The sea."], "scores": score_tags(obs, 2), "observations": obs,
        "merge_map": {}, "alignment": alignment,
        "usage": {"input_tokens": 10, "output_tokens": 5}, "cost_usd": 0.0001,
        "image_jpeg": prepare_image(buf.getvalue()),
    }


def _app():
    return AppTest.from_file(APP, default_timeout=120)


def test_page_renders_empty_with_subtitle_and_tabs():
    at = _app().run()
    assert not at.exception
    assert any(SUBTITLE in m.value for m in at.markdown)
    assert [t.label for t in at.tabs] == ["Analyze", "How certainty works"]
    assert any(t.label == "Creative brief" for t in at.text_area)


def test_result_refilters():
    at = _app()
    at.session_state["result"] = _fake_result()
    at.run()
    assert not at.exception
    assert any("Tags (2 of 2)" in h.value for h in at.subheader)
    at.radio[0].set_value("Certainty threshold").run()
    next(s for s in at.slider if s.label.startswith("Minimum certainty")).set_value(80).run()
    assert not at.exception
    assert any("Tags (1 of 2)" in h.value for h in at.subheader)


def test_alignment_renders():
    at = _app()
    at.session_state["result"] = _fake_result(with_alignment=True)
    at.session_state["brief"] = BRIEF
    at.run()
    assert not at.exception
    assert at.metric[0].value == "+0.25"
    assert any("Show the fabric up close." in m.value for m in at.markdown)
    assert not at.warning  # brief unchanged


def test_changed_brief_offers_reevaluation():
    at = _app()
    at.session_state["result"] = _fake_result(with_alignment=True)
    at.session_state["brief"] = BRIEF + " Priced like Patagonia."
    at.run()
    assert not at.exception
    assert at.warning
    assert any(b.label.startswith("Re-evaluate") for b in at.button)


def test_help_tab_explains_self_confidence():
    at = _app().run()
    text = " ".join(m.value for m in at.tabs[1].markdown)
    assert "Self-confidence" in text and "0 to 100" in text and "certainty =" in text
