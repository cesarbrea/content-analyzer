"""Altair chart builders. Each returns (chart, height_px) so callers can size the Streamlit element."""
import altair as alt
import pandas as pd

from core.brief import DIMENSIONS
from core.scoring import TagScore

ROW_PX = 30  # vertical space per bar, enough for a 13px label
LABEL_AXIS = dict(labelOverlap=False, labelFontSize=13, labelPadding=6)  # never hide labels


def tag_chart(shown: list[TagScore]) -> tuple[alt.LayerChart, int]:
    df = pd.DataFrame([s.to_dict() for s in shown])
    df["label"] = (df["certainty"] * 100).round().astype(int).astype(str) + "%"
    bars = alt.Chart(df).mark_bar().encode(
        # Domain past 100% leaves room for the value label on a full-length bar.
        x=alt.X("certainty:Q", title="Certainty", scale=alt.Scale(domain=[0, 1.08]),
                axis=alt.Axis(format="%", values=[i / 10 for i in range(11)])),
        y=alt.Y("tag:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260, **LABEL_AXIS)),
        tooltip=[
            alt.Tooltip("tag:N"),
            alt.Tooltip("certainty:Q", format=".0%"),
            alt.Tooltip("agreement:Q", format=".0%", title="agreement across runs"),
            alt.Tooltip("mean_self_confidence:Q", format=".0%", title="self-confidence"),
            alt.Tooltip("runs_seen:Q", title="runs seen"),
            alt.Tooltip("evidence:N"),
        ],
    )
    text = bars.mark_text(align="left", dx=3, fontSize=12).encode(text="label:N")
    h = max(120, ROW_PX * len(df))
    return (bars + text).properties(height=h), h + 40


def alignment_chart(alignment: dict) -> tuple[alt.LayerChart, int]:
    adf = pd.DataFrame([{"dimension": d.capitalize(), "score": v["score"], "rationale": v["rationale"]}
                        for d, v in alignment["dimensions"].items()])
    adf["label"] = adf["score"].map(lambda s: f"{s:+.2f}")
    order = [d.capitalize() for d in DIMENSIONS]
    base = alt.Chart(adf).encode(y=alt.Y("dimension:N", sort=order, title=None, axis=alt.Axis(**LABEL_AXIS)))
    bars = base.mark_bar().encode(
        # Padded domain keeps "-1.00"/"+1.00" labels clear of the axis labels and chart edge.
        x=alt.X("score:Q", title="Alignment (-1 to +1)", scale=alt.Scale(domain=[-1.25, 1.25]),
                axis=alt.Axis(values=[-1, -0.5, 0, 0.5, 1], format="+.1f")),
        color=alt.condition("datum.score >= 0", alt.value("#2e7d5b"), alt.value("#c0504d")),
        tooltip=["dimension", alt.Tooltip("score:Q", format="+.2f"), "rationale"],
    )
    pos = base.mark_text(align="left", dx=4).encode(x="score:Q", text="label:N").transform_filter("datum.score >= 0")
    neg = base.mark_text(align="right", dx=-4).encode(x="score:Q", text="label:N").transform_filter("datum.score < 0")
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#888").encode(x="x:Q")
    h = len(adf) * ROW_PX + 40
    return (bars + zero + pos + neg).properties(height=h), h + 40
