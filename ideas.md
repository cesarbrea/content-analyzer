# Creative Content Analyzer: ideas log

Ideas the user wants to keep in mind. **They are not in `plan.md` and are not planned.** The purpose of this file:

1. Record the ideas and an honest first evaluation of each.
2. Act as a watch-list. While the app evolves, if a change would make one of these harder to build later, Claude should **say so before making the change** and suggest an alternative (see "Design watch-outs" below).

Logged 2026-10-16. Evaluations are first impressions, not research. Where something rests on a source, the source is named.

---

## Summary

| # | Idea | Value | Effort | Main dependency |
|---|---|---|---|---|
| 1 | Compare ads to **customer sentiment** (wants and concerns), not just to a brief | High | Medium | A source of customer text, and a "reference" concept in the app |
| 2 | Compare ads to **product strategy**: product groups and target segments; semantic distance | High | Medium to high | Structured product and segment profiles; shared tag vocabulary (plan Phase 4b) |
| 3 | Use **consumer-profile datasets** such as Twin-2K-500 to simulate or profile audiences | Medium; promising but unproven | High | Ideas 1 and 2; validation against real results |

All three share one change in thinking: today the app compares an asset to **one kind of reference, the creative brief**. These ideas make "the reference" a general thing, with the brief as one type.

---

## Idea 1: Evaluate ads against customer sentiment

**The idea (user):** besides the campaign brief, compare one ad or several ads against a scrape and/or a synthesis of customer sentiment. Are our ads speaking to what customers want or worry about?

**My evaluation**

- **Fits the app well.** Tagging, caption and the story reading describe the asset on their own and don't use the brief. Only the alignment step uses the brief, so a second kind of reference mostly means a second alignment step.
- **The dimensions change.** The current four (customer, context, product, style) are built around a brief. A sentiment comparison needs different ones, for example: *wants addressed*, *concerns addressed or aggravated*, *language and tone vs how customers talk*, *unmet needs left untouched*. The dimensions should be data, not fixed constants.
- **Add a "voice of customer" step before comparing.** Don't send thousands of raw reviews with every ad. First turn the source text into a structured summary once: themes, how often each appears, sentiment, and representative quotes. Then compare each ad to that summary. This is cheaper, repeatable, and lets you inspect what the ad is being judged against.
- **Sourcing is the hard part, not the AI.**
  - Scraping reviews or social posts can breach site terms and raises privacy questions. Safer sources: data you already have (surveys, support tickets, review exports you are licensed to use), or a licensed dataset.
  - "Synthesis" (Claude summarising text you supply) is fine. Claude inventing sentiment with no source is not; label it clearly if ever offered.
  - Review and social data skew toward extreme opinions. The summary should record source, date range and sample size, and the output should say so.
- **Multiple ads:** the interesting output is a comparison across ads (which one speaks most to a given want or concern). That needs saved results across assets, which is already planned (Phase 4) but not built. Cost grows as ads × references, so keep each comparison cheap.
- **Risks:** the comparison will sound convincing whatever the quality of the source text. The report should always show the evidence it used.

---

## Idea 2: Evaluate ads against product strategy

**The idea (user):** as a retailer with, say, three product groups aimed at three segments, measure the **semantic distance** between my ads and the attributes of my products, or the attributes and preferences of my target consumers.

**My evaluation**

- **A strong use.** The question it answers is "which product or segment is this ad actually speaking to, and is that the one we intended?" The natural output is an **ads × segments matrix** (and ads × product groups), which can show an ad drifting toward the wrong segment.
- **Two ways to measure "semantic distance", and I'd combine them:**
  1. **Claude-judged fit** (what the app does today): readable, with reasons, good for a handful of ads. Slower and costlier at scale, and scores are not calibrated.
  2. **Embedding distance:** convert the ad's description (caption, tags, story) and each product or segment description to vectors and measure closeness. Cheap and consistent at scale. But it measures *topical similarity*, not persuasion or fit, and it is hard to explain to a client. Claude doesn't produce embeddings, so this needs a local model (like Whisper) or another provider. That conflicts with the "one model" decision (plan §15) and should be a deliberate choice.
- **The tag vocabulary can serve as the shared space.** Plan Phase 4b already aims to give every asset the same canonical tags ("sailboat" and "sailing boat" are one feature). If products and segments are also described in that vocabulary, each becomes a weighted tag vector and distances between ads, products and segments can be computed directly and explained ("this ad shares 6 of the segment's top 10 attributes"). This is the main reason to build the vocabulary well.
- **Needs structured inputs the app does not have today:** a product catalog or product-group definitions, and segment profiles (needs, attitudes, language). Someone has to supply and maintain them; the first version can be text the user pastes per group or segment.
- **Risks:** segment definitions are often vague, and "semantic distance" can look more precise than it is. Present it as a ranking and a screen, and validate against how ads actually performed (plan §18, performance modelling).

---

## Idea 3: Use consumer-profile datasets (e.g. Twin-2K-500)

**The idea (user):** leverage datasets that profile consumers, such as the one in https://arxiv.org/abs/2505.17479.

**What that source is (from its arXiv abstract page; I did not read the full paper):** *Twin-2K-500: A dataset for building digital twins of over 2,000 people based on their answers to over 500 questions* (Toubia, Gui, Peng, Merlau, Li, Chen). 2,058 US participants, four survey waves, about 500 questions each, covering demographic, psychological, economic, personality and cognitive measures, replications of behavioural-economics experiments and a pricing survey (average 2.42 hours per participant). Described as publicly available under **CC BY 4.0**.

**My evaluation**

- **A possible use:** each participant's answers can be turned into a profile, and Claude can be asked how that person would react to an ad ("a digital twin"). Run across many participants and grouped by segment, this gives a *simulated panel*: a cheap, early read of which segments an ad resonates with, before spending on real research.
- **Why I'd be cautious:**
  - It is **simulation, not research.** How faithfully a language-model twin matches a real person is exactly what such a dataset exists to test. I haven't read the paper's results, so check its fidelity findings before relying on this.
  - **Survey answers are not purchase behaviour.** Participants are US-based and a particular sample. They may not resemble a given retailer's customers.
  - **Cost and volume:** one call per participant per ad is 2,058 calls per ad. We would sample or cluster participants into a handful of archetypes.
  - **Licence and ethics:** CC BY requires attribution. Even a public individual-level dataset should be handled carefully and never presented as real consumer testing.
  - **Needs ground truth.** The only way to know whether the simulated reactions mean anything is to compare them with real outcomes (plan §18).
- **A lower-risk first step:** use the dataset to build *segment profiles* (attributes and preferences) for idea 2, rather than simulating individuals.

---

## Design watch-outs

Claude: **warn the user and suggest an alternative before** making a change that goes against any of these.

**Keep doing (already true):**
1. **Asset analysis stays independent of any reference.** Tagging, captions and the story reading do not use the brief. Do not feed the brief, or any reference, into the tagging or story prompts. That keeps one analysis reusable for many comparisons.
2. **Comparisons re-run without re-analysing the asset.** Re-evaluate already works from stored frames. Keep that property.
3. **Reports and charts are pure functions of data.** `build_report` and `build_deck` take a result dict, and `alignment_chart` takes the dimension order as a parameter. Don't couple them to `st.session_state`.
4. **Dimensions are data in the result** (a name to score and rationale mapping), which story scores already use.

**Watch, and fix when convenient:**
5. **`DIMENSIONS` in `core/brief.py` is a fixed constant** imported by the charts, the "How certainty works" tab and the report. Other comparisons need their own dimensions, so avoid importing it into new places. Prefer reading dimension names from the result.
6. **Wording that assumes "brief":** the `alignment` result key, the `brief` field stored inside it, the alignment prompt text, and UI and report labels. Fine for now; avoid spreading it into new code and data formats. A future shape like `{reference_type, reference_id, dimensions, ...}` would be easy to move to if we don't over-specialise now.
7. **Results exist only in the session.** Multi-ad comparison and any "ads × references" matrix need saved results. When Phase 4 (SQLite) is designed, store **assets, analyses and comparisons separately**, with a reference table that is not brief-specific (type, text, source, date, sample size).
8. **One asset at a time in the UI.** Don't bake that assumption deeper (for example into the PDF and deck structure) without noting that multi-asset reports will need a different layout.
9. **The shared tag vocabulary (Phase 4b) is the key enabler for idea 2.** Protect: stable `asset_key`, canonical merging across assets, `prompt_version` and model recorded with every analysis.
10. **Cost scales as assets × references.** Keep each comparison call small and cache anything reusable (frames, summaries of the reference).
11. **Single-model decision (plan §15).** Embeddings (idea 2) would need a local model or another provider. Flag it when it comes up rather than slipping it in.
12. **Provenance and confidentiality of reference data.** When references are added (customer text, product data, datasets), store where they came from and when, and don't send customer data anywhere without the user's agreement. Scraping needs a terms-of-service check first.

---

## Open questions for the user (when ready to pick one up)

- Which reference first: customer sentiment from text you already have, or product and segment descriptions?
- Do you have, or can you get, licensed customer text and product or segment profiles? Any client or AlixPartners data-handling rules that apply?
- Is a ranking-and-explanation output enough, or do you need numbers you can defend (which needs validation against real results)?
- Single ads, or sets of ads (campaigns, competitors)?
