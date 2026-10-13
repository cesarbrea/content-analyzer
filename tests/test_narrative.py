import core.narrative as nar
from core.video import pick_timestamps


def _story(with_brief):
    base = dict(logline="A host shops.", beats=[nar.Beat(start=0, end=3, summary="Intro", evidence="frame 0:00")],
                characters=[nar.Character(label="host", role="lead", description="young woman", first_seen=0.0,
                                          presence="central", speaks=True)], arc="hook, middle, CTA", gaps=["music"])
    if not with_brief:
        return nar.Story(**base)
    sc = lambda x: nar.NarrativeScore(score=x, rationale="r")
    return nar.StoryWithBrief(**base, plot=sc(2.0), characters_fit=sc(-0.5), structure=sc(0), product_timing=sc(1),
                              suggestions=["Show the product by 0:05"])


def _fake(monkeypatch, with_brief):
    seen = {}

    def parse_call(call_type, fmt, messages, system, effort, **kw):
        seen["fmt"] = fmt
        return _story(with_brief), {"input_tokens": 10, "output_tokens": 5}
    monkeypatch.setattr(nar, "parse_call", parse_call)
    return seen


def test_story_without_brief_has_no_scores(monkeypatch):
    seen = _fake(monkeypatch, False)
    out, u = nar.read_story([(0.0, b"x")], None, False, brief="  ")
    assert seen["fmt"] is nar.Story and "scores" not in out and out["logline"] == "A host shops."


def test_story_with_brief_scores_are_clamped_and_named(monkeypatch):
    seen = _fake(monkeypatch, True)
    out, _ = nar.read_story([(0.0, b"x")], None, False, brief="Target parents")
    assert seen["fmt"] is nar.StoryWithBrief
    assert list(out["scores"]) == list(nar.NARRATIVE_DIMENSIONS)
    assert out["scores"]["plot"]["score"] == 1.0 and out["scores"]["characters"]["score"] == -0.5
    assert out["suggestions"] == ["Show the product by 0:05"]


def test_story_frames_denser_than_tagging_frames_and_capped():
    short = pick_timestamps(30, [], 0.75, 4, 60)
    assert len(short) == 40 and short == sorted(short)
    assert len(pick_timestamps(300, [], 0.75, 4, 60)) == 60
    assert len(pick_timestamps(30, [])) == 10


def test_story_refuses_images_and_empty_input(monkeypatch):
    import pytest
    called = []
    monkeypatch.setattr(nar, "parse_call", lambda *a, **k: called.append(1))
    for bad in ([], [(None, b"x")]):
        with pytest.raises(ValueError):
            nar.read_story(bad, None, False)
    assert not called
