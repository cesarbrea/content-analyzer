"""Content Analyzer. Run with: streamlit run app.py"""
import json
from dataclasses import asdict

import pandas as pd
import streamlit as st

from certainty_help import render_certainty_help
from charts import alignment_chart, tag_chart
from core import config
from core.analyze import analyze_image
from core.brief import draft_brief, evaluate_alignment
from core.llm import ClaudeCallError
from core.scoring import filter_tags

st.set_page_config(page_title="Content Analyzer", layout="wide")
st.title("Content Analyzer")
st.markdown("This application describes and enhances tags for visual and audio content, and evaluates "
            "this content for conformance with a creative brief on multiple dimensions.")


# ---------------------------------------------------------------- callbacks (run before the page redraws)

def _on_draft():
    st.session_state.pop("draft_error", None)
    desc = st.session_state.get("product_desc", "").strip()
    if not desc:
        st.session_state["draft_error"] = "Enter a product description first."
        return
    try:
        text, u = draft_brief(desc)
        st.session_state["brief"] = text
        cost = config.cost_usd(config.MODEL, u["input_tokens"], u["output_tokens"])
        st.session_state["draft_note"] = f"Draft added to the brief below (${cost:.3f}). Edit it as needed."
    except Exception as e:
        st.session_state["draft_error"] = f"Drafting failed: {e}"


def _on_reevaluate():
    r = st.session_state["result"]
    try:
        alignment, u = evaluate_alignment(r["image_jpeg"], r["caption"], r["scores"],
                                          st.session_state.get("brief", ""), r["filename"])
    except Exception as e:
        st.session_state["align_error"] = f"Evaluation failed: {e}"
        return
    st.session_state.pop("align_error", None)
    r["alignment"] = alignment
    r["usage"]["input_tokens"] += u["input_tokens"]
    r["usage"]["output_tokens"] += u["output_tokens"]
    r["cost_usd"] = config.cost_usd(r["model"], r["usage"]["input_tokens"], r["usage"]["output_tokens"])


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Settings")
    st.caption(f"Model: `{config.MODEL}`")
    k = st.slider("Runs per asset (K)", 1, 5, config.DEFAULT_K,
                  help="Each asset is analyzed K times independently. See the 'How certainty works' tab.")
    has_brief = bool(st.session_state.get("brief", "").strip())
    est = (config.EST_COST_PER_RUN * k + config.EST_COST_MERGE
           + (config.EST_COST_ALIGNMENT if has_brief else 0))
    st.caption(f"Estimated cost: ~${est:.3f} per image" + (" (incl. brief alignment)" if has_brief else ""))

tab_analyze, tab_help = st.tabs(["Analyze", "How certainty works"])

# ---------------------------------------------------------------- Analyze tab

with tab_analyze:
    st.subheader("1. Creative brief (optional)")
    with st.expander("Draft a brief from a product description"):
        st.text_area("Product description", key="product_desc", height=120,
                     placeholder="e.g. A line of shirts for middle-aged and elderly sailors, using a fabric that "
                                 "vents heat and moisture midday and insulates as temperatures drop. "
                                 "Priced like Patagonia.")
        st.button("Draft brief", on_click=_on_draft)
        if "draft_error" in st.session_state:
            st.error(st.session_state["draft_error"])
        elif "draft_note" in st.session_state:
            st.success(st.session_state.pop("draft_note"))
    st.text_area("Creative brief", key="brief", height=260,
                 placeholder="Paste a creative brief here (or draft one above). When a brief is present, each "
                             "asset is scored against it on customer, context, product, and style.")

    st.subheader("2. Asset")
    uploaded = st.file_uploader("Image", type=["jpg", "jpeg", "png", "webp", "gif"])

    c1, c2 = st.columns([1, 2])
    with c1:
        mode_label = st.radio("Output limit", ["Top N", "Certainty threshold"], horizontal=True)
    with c2:
        if mode_label == "Top N":
            mode, value = "top_n", st.slider("Max tags", 1, config.MAX_TAGS_REQUESTED, config.DEFAULT_TOP_N)
        else:
            mode, value = "threshold", st.slider("Minimum certainty (%)", 0, 100, config.DEFAULT_THRESHOLD)

    if st.button("Analyze", type="primary", disabled=uploaded is None):
        with st.status(f"Analyzing {uploaded.name}…", expanded=True) as status:
            try:
                st.session_state["result"] = analyze_image(
                    uploaded.getvalue(), uploaded.name, k,
                    brief=st.session_state.get("brief", ""), on_progress=st.write)
                st.session_state.pop("align_error", None)
                status.update(label="Done", state="complete", expanded=False)
            except ClaudeCallError as e:
                status.update(label=f"Failed: {e}", state="error")
            except Exception as e:  # surface anything else in the UI for debugging
                status.update(label=f"Failed: {type(e).__name__}: {e}", state="error")
                st.exception(e)

    # ---- Results (changing the output limit re-filters here without calling the API) ----
    result = st.session_state.get("result")
    if result:
        st.divider()
        shown = filter_tags(result["scores"], mode, value)

        left, right = st.columns([1, 2])
        with left:
            st.image(result["image_jpeg"], caption=result["filename"])
            u = result["usage"]
            st.caption(f"{result['model']} · K={result['k']} · {u['input_tokens']:,} in / "
                       f"{u['output_tokens']:,} out tokens · ${result['cost_usd']:.4f}")
        with right:
            st.subheader("Caption")
            st.write(result["caption"])
            st.subheader(f"Tags ({len(shown)} of {len(result['scores'])})")
            if not shown:
                st.info("No tags meet the current limit.")
            else:
                chart, h = tag_chart(shown)
                st.altair_chart(chart, width="stretch", height=h)

        # ---- Brief alignment ----
        st.divider()
        st.subheader("Creative brief alignment")
        current_brief = st.session_state.get("brief", "").strip()
        alignment = result.get("alignment")

        if "align_error" in st.session_state:
            st.error(st.session_state["align_error"])

        if alignment is None:
            if current_brief:
                st.info("This asset was analyzed without a brief.")
                st.button("Evaluate against the current brief", on_click=_on_reevaluate)
            else:
                st.caption("Add a creative brief above to score this asset against it.")
        else:
            if current_brief and current_brief != alignment["brief"].strip():
                st.warning("The brief has changed since this evaluation.")
                st.button("Re-evaluate against the current brief", on_click=_on_reevaluate)

            a1, a2 = st.columns([1, 3])
            with a1:
                st.metric("Overall alignment", f"{alignment['overall']:+.2f}",
                          help="Mean of the four dimension scores. -1 = contradicts the brief, "
                               "0 = absent / not addressed, +1 = fully conforms.")
            with a2:
                chart, h = alignment_chart(alignment)
                st.altair_chart(chart, width="stretch", height=h)

            for d, v in alignment["dimensions"].items():
                st.markdown(f"**{d.capitalize()} ({v['score']:+.2f}):** {v['rationale']}")

            st.markdown("**Suggestions to align more closely with the brief**")
            for s in alignment["suggestions"]:
                st.markdown(f"- {s}")

            with st.expander("Brief used for this evaluation"):
                st.text(alignment["brief"])

        # ---- Debug details ----
        st.divider()
        with st.expander("Tag details"):
            st.dataframe(pd.DataFrame([s.to_dict() for s in result["scores"]]), width="stretch")
        with st.expander("Merged variants"):
            st.write(result["merge_map"] or "No variants were merged.")
        with st.expander("Raw data (debug)"):
            debug = {k_: v for k_, v in result.items() if k_ not in ("image_jpeg", "scores", "observations")}
            debug["observations"] = [asdict(o) for o in result["observations"]]
            st.code(json.dumps(debug, indent=2, ensure_ascii=False), language="json")

# ---------------------------------------------------------------- How certainty works tab

with tab_help:
    render_certainty_help(k)
