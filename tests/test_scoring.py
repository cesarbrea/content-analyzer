import pytest

from core.merge import normalize
from core.scoring import Observation, filter_tags, score_tags


def obs(run, tag, conf):
    return Observation(run, tag, tag, "visual", conf, "")


def test_agreement_and_certainty():
    o = [obs(0, "sailboat", 90), obs(1, "sailboat", 80), obs(2, "sailboat", 100), obs(0, "gull", 40)]
    scores = {s.tag: s for s in score_tags(o, k=3)}
    assert scores["sailboat"].agreement == 1.0
    assert scores["sailboat"].mean_self_confidence == pytest.approx(0.9)
    assert scores["sailboat"].certainty == pytest.approx(0.6 * 1.0 + 0.4 * 0.9)
    assert scores["gull"].agreement == pytest.approx(1 / 3)
    assert scores["gull"].certainty == pytest.approx(0.6 / 3 + 0.4 * 0.4)


def test_duplicate_in_one_run_counts_once():
    o = [obs(0, "sea", 60), obs(0, "sea", 90)]
    s = score_tags(o, k=2)[0]
    assert s.runs_seen == 1 and s.agreement == 0.5 and s.mean_self_confidence == pytest.approx(0.9)


def test_k1_uses_self_confidence_only():
    s = score_tags([obs(0, "sky", 70)], k=1)[0]
    assert s.certainty == pytest.approx(0.7)


def test_sorted_and_filtered():
    o = [obs(0, "a", 20), obs(0, "b", 90), obs(0, "c", 55)]
    scores = score_tags(o, k=1)
    assert [s.tag for s in scores] == ["b", "c", "a"]
    assert [s.tag for s in filter_tags(scores, "top_n", 2)] == ["b", "c"]
    assert [s.tag for s in filter_tags(scores, "threshold", 55)] == ["b", "c"]


def test_normalize():
    assert normalize("  Sailing  Boat! ") == "sailing boat"
    assert normalize("mid_day") == "mid day"
