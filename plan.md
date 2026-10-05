# Content Analyzer — Build Plan

_Plan written 2026-09-29 from the planning conversation and the Loom walkthrough of the earlier variant. Last updated 2026-10-05._

**Progress:** Phases 0–3 are complete, and **Phase 6 (video) is done for `.mp4`**; it was moved ahead of Phases 4–5 so a screen-recorded ad could be analyzed. Working now: image and `.mp4` tagging with certainty scores, local speech transcription, the "How certainty works" tab, brief alignment, and brief drafting. **Next: Phase 4** (SQLite persistence, History, CSV/JSON export), then **Phase 4b** (library vocabulary and model-ready feature export for propensity and media mix models, §18). **Under discussion:** analyzing YouTube URLs (§17). See §12 for phase status and §16 for the change log.

---

## 1. Purpose

A local web app that takes images, videos, or zip archives of them, looks at the **visuals and audio**, and produces:
- a short **caption** per asset, to check what the AI "sees";
- short (1–2 word) **emergent descriptive tags**, each with a **certainty score**, grouped into categories;
- when a creative brief is provided, an **alignment assessment** with **improvement suggestions**.

It also helps **draft a creative brief** from a product description.

The app serves **two uses** (the second added 2026-10-05, from the project README):

1. **Creative optimization (a "muse" for creative teams):** understand the properties of campaign assets, how well they fit the brief, and how to improve them. The AI acts as a **creative aid, not a replacement** for the people doing the creative work.
2. **Creative features for performance modelling:** turn assets into **enriched, structured tags** (features) that can be joined to creative performance data. The aim is to understand which creative attributes drive response, and to add creative features to **customer-response propensity models** and **media mix models**, which today usually treat creative as a black box.

Use 2 doesn't change the analysis itself. It shapes how results are **stored and exported** (§9–10, §18): stable asset IDs to join on, a tag vocabulary that is consistent *across* assets, numeric feature values, and records of which model and prompt produced each value.

---

## 2. Background: earlier variant (Loom walkthrough)

_"Impact Foundry Image Analysis and Tagging for Creative Optimization in Advertising"_ (~5 min). What the earlier app did, and what carries forward:

| Earlier variant | In this plan |
|---|---|
| Short creative brief (~185 words) pasted in. Example: shirts for middle-aged and elderly male and female sailors, with fabric that vents heat and moisture midday and insulates as temperatures drop, priced like Patagonia | Brief text area (§6.6) |
| Brief structure and draft produced with a general LLM beforehand | **Brief drafting helper** built in (§6.7) |
| **Caption** first, to confirm the model understands the image | Caption per asset (§6.4) |
| First-order **features** extracted | Emergent tags (§6.4) |
| Model asked for **confidence** per feature; no explicit algorithm; checked by **re-running** and seeing whether features held | Formalized: **self-consistency across K runs + self-rated confidence** (§7) |
| Idea: **group features into categories** (objects, styles, …) | Emergent categories (§6.5) |
| **Overall alignment on a −1 to +1 scale** (demo: 0.7) | Same scale (§6.6) |
| Dimensions: **customer, context (environment), product, style** (realist vs cartoon/abstract) | The four fixed dimensions (§6.6) |
| **Specific suggestions** (show the product closer; show the temperature-regulating benefit, e.g. one person inside and one outside on a boat; get closer to the subject) | Suggestions per asset (§6.6) |
| Video mentioned as feasible but more compute-heavy | Video in scope; cost estimate shown before running (§8) |
| Tags later used to **tag the asset library** | Saved results + export (§9–10) |

---

## 3. Scope

### In scope (v1)
| # | Capability |
|---|---|
| 1 | Upload one image, one video, or a `.zip` containing images and/or videos |
| 2 | **Caption** per asset |
| 3 | Visual tagging of images and video frames |
| 4 | Audio for videos: **speech topics** (local transcript, always on) and **sound events** (music, wind, crowd; **optional module**) |
| 5 | **Emergent** tags (no fixed list), **grouped into emergent categories** |
| 6 | Output limit, chosen by the user as either **max number of tags (Top-N)** or **certainty threshold (≥ X%)** |
| 7 | **Horizontal bar chart per file**, showing tags by certainty, colored by category |
| 8 | **"How certainty works"** tab |
| 9 | **Brief alignment**, run automatically on **every file** when a brief is present: 4 fixed dimensions, −1…+1, overall score, suggestions |
| 10 | **Brief drafting helper**: product description → structured brief → editable text in the brief box |
| 11 | **Saved results** (History) and **export** (CSV + JSON) |
| 12 | Runs locally on the laptop, single user |

### Out of scope for now
Auth and multi-user, cloud hosting, job queues, rate limiting, billing, fixed or client taxonomies, brief upload (.docx/.pdf), configurable alignment dimensions, batch-level summary views.

---

## 4. Guiding principle: maximum simplicity

Chosen to make debugging easy:
- **One language (Python), one process.** No separate front end or build step.
- **Streamlit** for the UI (`streamlit run app.py`).
- **SQLite** file plus a local `data/` folder. No database server.
- **Synchronous processing** with a progress bar. No background workers.
- Every analysis step is a **plain function**, callable from a script or test without the UI.
- Log every Claude request and response (minus image bytes) to `data/logs/` so any tag can be traced back.

### Tech stack
| Concern | Choice | Notes |
|---|---|---|
| Runtime | **Python 3.12** (3.12.10) in a project `.venv` | Installed |
| UI | Streamlit (1.64), with tabs inside one page | |
| Charts | Altair (ships with Streamlit) | Horizontal and diverging bars, tooltips; builders in `charts.py` |
| LLM | Anthropic Python SDK (`anthropic` 1.9) | Structured outputs via `client.messages.parse()` + Pydantic; 90 s request timeout, 2 retries |
| Images | Pillow | Resize to ≤1568 px on the long edge |
| Video frames and audio extraction | **ffmpeg** (`winget install Gyan.FFmpeg`) | Via `subprocess`; installed (9.0.2). `core/video.py` finds it even when the process started before ffmpeg was on PATH (checks the user PATH in the registry and the WinGet packages folder) |
| Speech-to-text | `faster-whisper` (CTranslate2; **no PyTorch needed**) | `base` model, CPU, int8, voice-activity filter on. Model downloaded once (~150 MB) from Hugging Face into the user cache. Audio is passed as a NumPy array read from ffmpeg's 16 kHz WAV, which skips faster-whisper's PyAV decoder (it fails with newer PyAV: `unexpected keyword argument 'metadata_errors'`) |
| Corporate network TLS | `truststore` | Makes Python trust the Windows certificate store, needed because the AlixPartners network re-signs HTTPS traffic (Hugging Face download failed with `self-signed certificate in certificate chain`). Certificate checking stays on |
| Sound events (**optional**) | Audio Spectrogram Transformer (`MIT/ast-finetuned-audioset-10-10-0.4593`) via `transformers` + `torch` | Separate `requirements-audio.txt` (~2 GB). App detects whether it's installed and hides or disables the option if not |
| Storage | SQLite (`sqlite3` stdlib) + `data/` | |
| Config | `.env` (`ANTHROPIC_API_KEY`; optional `CA_MODEL`) + `core/config.py` (defaults, weights, prices, cost estimates) | `.env` is gitignored; `.env.example` shows the format |
| Tests | `pytest`; Streamlit `AppTest` for the UI | No API calls in tests |

---

## 5. Model

**One model for everything: `claude-sonnet-5`** ($2 / $10 per 1M input/output tokens), set in config so it can be swapped later (e.g. `claude-opus-5` for more accuracy, `claude-haiku-4-5` for lower cost).

| Call | Effort | Notes |
|---|---|---|
| Caption + tags (×K) | `low` | High volume; mostly perception |
| Tag merge (+ categorization, Phase 5) | `low` | Text only, cheap |
| Brief alignment + suggestions | `medium` | Needs judgment; once per asset |
| Brief drafting | `medium` | Once per brief |

Adaptive thinking on (`thinking: {type: "adaptive"}`), effort via `output_config.effort`.

**Measured cost (Sonnet 5, sample image, 2026-09-29/30):**

| Item | Cost |
|---|---|
| One tagging run | ≈ $0.016 |
| Merge call | ≈ $0.004 |
| **Image at K = 3, no brief** | **≈ $0.054** (7.6K input / 3.8K output tokens) |
| Brief alignment | ≈ $0.012 per image |
| **Image at K = 3, with brief** | **≈ $0.066** |
| Drafting a brief | ≈ $0.007 |
| **Short video, per tagging run** (~9 frames at 1024 px; 8.4K input / 1.2K output tokens) | ≈ $0.029 |
| Video merge call | ≈ $0.011 |
| Video brief alignment | ≈ $0.023 |
| **Short video at K = 3, with brief** (measured 2026-10-05) | **≈ $0.12** (no brief ≈ $0.10) |

Output tokens, which include Claude's reasoning, are the main cost driver for images; for video, the frames make input the larger share. These figures are set in `core/config.py` (`EST_COST_*`) and used for the sidebar estimate and the help tab.

**Original estimate** (made before measuring, for reference): ≈ $0.03–0.04 per image and ≈ $0.15 per video (~10 frames at full size plus transcript, ≈ 17K input tokens per call), both at K = 3 plus alignment. The video estimate came down because frames are sent at 1024 px instead of 1568 px.

---

## 6. Processing pipeline

```
Upload ─► Ingest ─► Prep ─► Caption+Tags (K runs) ─► Merge ─► Score ─► Categorize ─► Filter ─► [Brief alignment] ─► Save ─► Charts/Export
```

### 6.1 Ingest
- Accepted: images `.jpg .jpeg .png .webp .gif` (first frame); videos `.mp4 .mov .m4v .webm .avi`; `.zip`.
- Zip: extract to a per-run temp folder. Guard against path traversal (zip-slip). Skip `__MACOSX/` and hidden files. Recurse into subfolders. Unsupported files are listed as skipped in the run summary.
- Configurable size limits (e.g. 50 MB per image, 1 GB per video, 2 GB per zip).
- Each asset gets an ID and a copy or thumbnail in `data/assets/`.

### 6.2 Image prep
Fix EXIF orientation, convert to RGB, resize to ≤1568 px on the long edge.

### 6.3 Video prep ✅ (`.mp4`; `core/video.py`, `core/audio.py`)
1. **Probe** with ffprobe: duration, size, whether there is an audio track.
2. **Frames:** ffmpeg scene-change detection (scene score > 0.3). The frame count is about one frame per 2 s, between 4 and 10 frames. The chosen frames are the opening shot, a frame 0.3 s after each cut, and then the evenly spaced points farthest from those already chosen; near-duplicates are dropped. With many cuts, an even spread of them is kept. Frames are resized to **1024 px** (vs 1568 for images) to keep cost down. Example: a 19 s ad with 4 cuts gave 9 frames.
3. **Audio:** ffmpeg → 16 kHz mono WAV, then:
   - **Speech (always on, local):** faster-whisper → timestamped segments + language. Audio never leaves the laptop; only the transcript text goes to Claude.
   - **Sound events (optional, Phase 7):** AST on ~10 s windows. Keep labels ≥ 0.15 probability.
4. Frames (each labelled "Frame at m:ss.s"), the transcript (or "No speech detected" / "no audio track"), and later sound events go into **one** Claude request per run, so the video is tagged as a whole. Tags use `source: speech` for things that come from the transcript; evidence cites frame times or quotes.
5. Claude is told to **ignore video player and screen-recording elements** (play/pause buttons, progress bars, browser chrome), because screen recordings of YouTube include them.
6. Only `.mp4` is accepted for now (`VIDEO_TYPES` in config). `.mov`, `.webm`, and others need only to be added to that list and tested.

### 6.4 Caption + tagging (Claude, K runs)
Structured output (Pydantic):
- `caption`: 1–2 sentences
- `tags[]`, where each tag has:
  - `tag` (1–2 words, lowercase, freely chosen)
  - `source`: `visual` | `speech` | `sound`
  - `self_confidence` 0–100 against this rubric (`CONFIDENCE_BANDS` in `core/tagger.py`, shared by the prompt and the help tab):
    - 90–100: clearly and centrally present; any viewer would agree
    - 70–89: clearly present but small, partial, or secondary
    - 40–69: plausible but ambiguous (distance, blur, occlusion, interpretation)
    - 0–39: speculative; include only if it would matter for advertising review
  - `evidence`: a short pointer (region, frame timestamp, or transcript quote)

The prompt covers subjects, people and *apparent* demographics, setting, activity, objects, product and apparel features, mood, and visual style. It asks for up to 25 tags and tells Claude to be calibrated rather than default to high numbers. The caption from run 1 is displayed; all captions are kept in the raw data.

For video the prompt adds: tag the video as a whole (rate brief or peripheral things lower), and tag what is said (topics, claims, benefits, calls to action, tone of voice), noting that transcripts are machine-generated. Images and videos share one code path: `tagger.media_blocks()` turns an asset into content blocks, which are used for both tagging and alignment.

The K runs are sent in parallel (thread pool). Progress updates are reported from the main thread so Streamlit can display them. Claude sometimes tags notable absences (e.g. "no people"); these are kept, since they're relevant to brief review.

### 6.5 Emergent categories _(Phase 5, not yet built)_
After merging (§7), one cheap call groups the canonical tags into **categories that Claude names itself** (e.g. *people, setting, objects, product, style, mood*). Categories color the bar chart and appear as a column in exports.

### 6.6 Brief alignment (automatic for every file when a brief is present)
- Brief pasted as text (or drafted, §6.7).
- **Scale:** +1 fully conforms · +0.5 mostly conforms, with clear gaps · **0 absent / not addressed / neutral** · −0.5 partly works against the brief · −1 directly contradicts.
- **Absence scores 0, not negative** (decided 2026-09-30). If the asset doesn't show something the brief calls for (no people, no product), that dimension scores exactly 0 and the rationale says what's missing. Negative scores are only for content that is present and works against the brief: young models for an older audience, a cartoon style when the brief calls for realism, a conflicting setting. The prompt states this rule explicitly for every dimension, because a first version still scored a missing product −0.5.
- **Fixed dimensions:**
  - **Customer:** does it show or speak to the target audience?
  - **Context:** is the environment/setting consistent with the brief?
  - **Product:** is the product represented well, including its key features and benefits?
  - **Style:** does the treatment fit (realist vs illustrated/abstract, tone, brand feel)?
- Output: per-dimension score + one-sentence rationale; **overall score** (equal-weighted mean); **3–5 concrete improvement suggestions**.
- Input: image/frames (plus transcript for video), the caption, **and** the merged tags with certainty, so the reasoning stays tied to what was detected. Claude is told to trust the image where it disagrees with the tags.
- Effort `medium`. It's a single judgment (not repeated K times), so small differences such as +0.6 vs +0.7 are noise. In testing, one dimension moved by 0.5 between two runs on the same image.
- Display: the **overall score** as a metric, a **diverging horizontal bar chart** (green ≥ 0, red < 0) with values labelled, the per-dimension rationales, the suggestions, and the brief used.
- **Re-evaluate:** if the brief is edited after analysis (or the asset was analyzed without one), a button re-scores only the alignment, without re-tagging (≈ $0.012).

### 6.7 Brief drafting helper
- A **"Draft a brief"** panel on the Analyze page: the user types a product description (free text: product, audience, key features, price positioning, tone).
- Claude returns a structured brief using a standard layout: *Objective · Target audience · Product & key benefits · Single-minded proposition · Tone & style · Setting / context · Mandatories · Success measures*. The prompt sets 150–250 words and a hard maximum of 250, because the first test came out at 282 words; the retest gave 240.
- Output is placed in the **brief text area for editing** before analysis. Sections map naturally onto the four alignment dimensions.
- _(Phase 4)_ Drafts will be saved with the run, or on their own if no analysis follows. They're not saved yet.

---

## 7. Certainty ("tagging accuracy") method

Claude doesn't give out calibrated probabilities, so certainty is **computed** from signals we can explain. This formalizes the earlier variant's informal check of re-running and seeing whether features held.

1. **Self-consistency (agreement):** analyze each asset **K times** independently (**default K = 3**, configurable 1–5). Agreement = share of runs in which the tag appeared.
2. **Self-rated confidence:** mean `self_confidence` over the runs where the tag appeared, scaled to 0–1.
3. **Tag merging:** normalize (lowercase, strip punctuation, collapse whitespace), then make **one cheap merge call** grouping synonyms and plural/word-order variants ("sailboat" / "sailing boat") under a canonical tag picked from the existing variants. Broader and narrower terms stay separate ("boat" ≠ "sailboat"). Code-based singularizing was dropped because it mangled words like "clothes" and "jeans"; the merge call handles plurals instead. The mapping is shown under **Merged variants**. If a tag appears twice in one run after merging, it counts once (the higher confidence is kept).
4. **Combined score:** `certainty = 0.6 × agreement + 0.4 × mean_self_confidence` (weights in `core/config.py`). With K = 1, certainty = self-confidence only, and the help tab says to treat it as uncalibrated.
5. **Sound-event tags** (when the optional module is on) come with real AST model probabilities, shown with a `sound (model)` source and explained separately.

**"How certainty works" tab** (`certainty_help.py`) covers: agreement; **self-confidence**, defined as Claude's own 0–100 rating, in each run, of how sure it is that the tag accurately describes the asset, shown with the exact rubric table; the combined formula; worked examples computed live by the scoring code; what the score does and doesn't mean (not a calibrated probability; runs aren't fully independent); how K trades steadiness against cost; and the brief-alignment dimensions, scale, and absence rule. All numbers come from live config.

_Later: calibrate against a hand-labelled set and add a reliability chart._

---

## 8. UI (Streamlit, one page with tabs)

**Header:** "Content Analyzer", with the subtitle: _"This application describes and enhances tags for visual and audio content, and evaluates this content for conformance with a creative brief on multiple dimensions."_

**Tabs:**
1. **Analyze** ✅
   - **1. Creative brief (optional)**
     - **Draft a brief from a product description** (expander): description → "Draft brief" → fills the brief box
     - **Creative brief** text area; when filled, alignment runs on every file
   - **2. Asset**
     - Uploader: images (jpg, jpeg, png, webp, gif) and **`.mp4` video**; zip in Phase 5
     - Output limit: radio **Top N** (1–25) or **Certainty threshold** (0–100%)
     - "Analyze" → step-by-step progress
   - **Results:**
     - image, or **video player** with duration / size / frame count · cost/tokens · **caption** · **tag certainty chart** (single color for now; colored by category in Phase 5; tooltips show agreement, self-confidence, runs seen, evidence)
     - _(video)_ **Frames sent to Claude** grid with timestamps · **Speech transcript** with timestamps (or "No speech detected. Music and sound effects aren't analyzed yet.")
     - **Creative brief alignment:** overall metric, diverging chart, rationales, suggestions, brief used, re-evaluate button
     - expanders: Tag details · Merged variants · Raw data (debug)
2. **How certainty works** ✅ (§7)
3. _(Phase 4)_ **History:** past runs (date, files, model, settings, tokens/cost). Reopen or delete.

**Sidebar:** model ID (display), K slider, cost estimate per image and per short video (includes alignment when a brief is present). Score weights and the frame cap are set in `core/config.py`, not the UI. A sound-event toggle comes in Phase 7.

**Charts:** 30 px per bar, 13 px labels, and Vega-Lite label hiding (`labelOverlap`) turned off, so every bar's label is always shown. Axes run slightly past the data range (certainty to 108%; alignment to ±1.25) so end-of-bar values aren't clipped.

Changing Top N or the threshold **re-filters the stored result** without calling Claude again.

---

## 9. Data model (SQLite) _(Phase 4, not yet built; results currently live in the Streamlit session only)_

- `runs` (id, created_at, model, **prompt_version**, k_runs, limit_mode, limit_value, brief_text, sound_events_enabled, input_tokens, output_tokens, est_cost_usd)
- `briefs` (id, run_id nullable, product_description, drafted_brief, created_at)
- `assets` (id, run_id, **asset_key**, **content_hash**, filename, kind, path, thumb_path, duration_s, caption, transcript, sound_events_json)
- `tag_observations` (asset_id, run_index, raw_tag, canonical_tag, source, self_confidence, evidence)
- `tags` (asset_id, canonical_tag, **feature** (library vocabulary term, §18), category, source, agreement, mean_self_confidence, certainty)
- `brief_scores` (asset_id, dimension, score, rationale)
- `brief_summary` (asset_id, overall_score, suggestions_json)
- **`vocabulary`** (feature, category, variants_json, first_seen, asset_count): the library-level vocabulary (§18)

The unfiltered tag list is stored in full; filtering happens at display and export time.

Added for performance modelling (use 2):
- **`asset_key`:** the ID used to join with performance data (ad ID, creative ID, or filename). It defaults to the filename and can be edited, because filenames rarely match the IDs in ad platforms.
- **`content_hash`:** a fingerprint of the file, so re-uploads of the same creative are recognized even under a different name.
- **`prompt_version`:** recorded with every run, together with the model. Features from different prompt or model versions shouldn't be mixed silently in a model.

## 10. Export _(Phase 4, not yet built)_
- **CSV (tags):** file, caption, tag, category, certainty, agreement, self-confidence, source, evidence.
- **CSV (alignment):** file, dimension, score, rationale, plus overall score and suggestions.
- **JSON:** full run: settings, brief, captions, transcripts, raw observations, merge mapping, categories, alignment.
- Export either the current filtered view or everything.
- **Feature matrix CSV (for modelling):** one row per asset (`asset_key`), one column per vocabulary feature, plus the four alignment dimensions, overall alignment, and asset metadata (kind, duration, model, prompt_version, run date). A feature is **0 when absent**; when present, the value is its **certainty** (0–1), with an option to export **binary** values (1 at or above a chosen certainty threshold) instead. **Every** feature is exported, not just the current Top N, so the columns are the same for every asset. Accompanied by a data dictionary (feature → category, variants, number of assets).
- **Long-format CSV (for modelling):** `asset_key, feature, category, source, certainty, agreement, self_confidence`, for tools that prefer tidy data.

---

## 11. Project layout

✅ = exists now; others are planned.

```
content_analyzer/
  app.py                    ✅ Streamlit entry: header, sidebar, Analyze + help tabs
  certainty_help.py         ✅ "How certainty works" tab content (live config values)
  charts.py                 ✅ Altair builders: tag_chart, alignment_chart
  core/
    config.py               ✅ env + defaults, weights, prices, cost estimates
    llm.py                  ✅ Claude client (timeout/retries), parse_call / text_call, JSONL logging
    images.py               ✅ resize/normalize
    tagger.py               ✅ media_blocks (image or frames+transcript), tag_asset, CONFIDENCE_BANDS rubric
    merge.py                ✅ normalization + synonym merge (categorization in Phase 5)
    scoring.py              ✅ certainty + filtering (pure functions)
    brief.py                ✅ brief drafting + alignment + suggestions, DIMENSIONS
    analyze.py              ✅ analyze_asset: prep (image/video) -> K runs -> merge -> score -> alignment
    video.py                ✅ find ffmpeg, probe, scene changes, pick_timestamps, frames, audio
    audio.py                ✅ faster-whisper transcription (optional AST sound events in Phase 7)
    ingest.py                  upload/zip handling (Phase 5)
    storage.py                 SQLite (Phase 4)
    export.py                  CSV/JSON (Phase 4)
  scripts/
    check_api.py            ✅ one-line API/key check
    try_image.py            ✅ run the pipeline on an image from the terminal; --make-sample
  tests/
    test_scoring.py         ✅ scoring, filtering, normalize
    test_app.py             ✅ UI renders (AppTest), re-filtering, alignment, help tab, video results; no API calls
    test_video.py           ✅ frame picking, media blocks, ffmpeg on a generated 4 s clip; no API calls
    assets/sample_sailboat.png ✅ synthetic test image
  data/                     gitignored: logs (db, assets from Phase 4)
  .env / .env.example       ✅ API key (gitignored) / format example
  requirements.txt          ✅
  requirements-audio.txt    ✅ optional: torch + transformers for sound events
  plan.md
```

**Run:** `.\.venv\Scripts\streamlit.exe run app.py` (after changing anything under `core/`, **restart** the app; a browser refresh keeps old modules in memory) · **Test:** `.\.venv\Scripts\python.exe -m pytest tests` · **CLI check:** `.\.venv\Scripts\python.exe scripts\try_image.py <image> [K]`

---

## 12. Build phases

| Phase | Deliverable | Done when | Status |
|---|---|---|---|
| 0 | **Environment setup:** Python 3.12, ffmpeg, `.venv`, `ANTHROPIC_API_KEY` in `.env`, `git init` | `python --version`, `ffmpeg -version`, and a one-line Sonnet 5 test call all succeed | ✅ 2026-09-29 |
| 1 | Single image → K runs → merge → certainty → caption + tag chart; Top-N/threshold toggle; token/cost logging | Chart renders; re-filtering makes no API calls; measured cost | ✅ 2026-09-29 (cost ≈ $0.054, above the $0.03–0.04 estimate, accepted) |
| 2 | "How certainty works" tab | Reads live config values; explains self-confidence | ✅ 2026-09-30 |
| 3 | Brief alignment (4 dimensions, −1…+1, suggestions, diverging chart) + **brief drafting helper** | Sailing-shirt description → drafted brief → image gives sensible scores and suggestions | ✅ 2026-09-30. Tested on a synthetic image and on a user photo of dinghy racers; still to do: test with the demo's Sunfish image |
| 4 | SQLite persistence, History tab, CSV/JSON export, saved brief drafts; **`asset_key` / `content_hash` / `prompt_version`** stored from the start | Past run reopens identically; exports open in Excel | **Next** |
| 4b | **Library vocabulary + model-ready export** (§18): cross-asset feature merge, editable vocabulary, feature-matrix and long-format CSVs with a data dictionary | Two assets with "sailboat" vs "sailing boat" land in the same column; the matrix loads cleanly into Python/R/Excel | After Phase 4 (needs saved results across assets) |
| 5 | Zip ingest (images) + emergent categories | Mixed zip with junk files handled cleanly; chart colored by category | |
| 6 | Video visual tagging (ffmpeg frames) + speech via faster-whisper | Tags cite frame timestamps or quotes | ✅ 2026-10-05 for `.mp4` (done before Phases 4–5 at the user's request). Tested with screen-recorded ads. Speech tested only on a no-speech ad so far |
| 7 | **Optional** sound-event module (AST) | App works with and without `requirements-audio.txt` installed | |
| 8 | Polish: error handling (API errors, bad files), logging | One failed asset doesn't break the run | Partly done: request timeout + retries, refusal / incomplete-output errors shown in the UI |

---

## 13. Risks and notes
- **Emergent tags vary run to run.** Merge quality drives certainty quality, so keep the mapping visible and unit-tested.
- **Emergent tags also vary asset to asset**, which matters for modelling: without a shared vocabulary, "sailboat" in one ad and "sailing boat" in another become different features. §18 addresses this.
- **Features for modelling are model outputs, not ground truth.** Certainty isn't calibrated, and a model or prompt change can shift values. Record `model` + `prompt_version`, and re-run the whole library under one version before fitting a model.
- **Cost scales with K × frames × files.** Show an estimate before each run, especially for large zips, since alignment runs on every file.
- **ffmpeg must be on PATH.** Check at startup and show a clear message if it's missing.
- **Apparent demographics** ("middle-aged", "elderly") are needed for customer alignment but are guessed from appearance. Label them as apparent.
- **Data handling:** assets, frames, and transcripts are sent to the Anthropic API. The user confirmed there are no restrictions.
- **Hung requests:** one request once stalled for ~7 minutes under the SDK's default 10-minute timeout. Now 90 s with 2 retries, so a stuck call fails visibly instead of looking like a freeze.
- **Laptop memory:** a background-started app was stopped once when memory ran low. If the app disappears, restart it with the run command in §11.
- **Corporate network (TLS inspection):** downloads from Python (e.g. Hugging Face models) fail certificate checks unless `truststore` is used. Any new download in future phases (e.g. the AST sound model) should go through the same path.
- **Library drift:** faster-whisper's PyAV-based decoder broke with the installed PyAV; worked around by passing raw audio. Pinning versions in `requirements.txt` would prevent surprises like this.
- **Streamlit module caching:** after code changes under `core/`, restart the app (a refresh caused an `ImportError` once).
- **Long videos:** the 10-frame cap is sized for 15–60 s ads. Longer videos are sampled more sparsely, and transcription takes longer on CPU.
- **Windows tooling note:** PowerShell 5.1's `Get-Content`/`Set-Content` reads and writes non-UTF-8 by default and garbled characters in `app.py` once. Edit source files with an editor, not PowerShell text replacement.

## 14. Later ideas (not v1)
- Brief upload (.docx/.pdf); configurable or brief-derived dimensions and weights.
- Batch-level views: tag frequency across a library, rank assets by alignment.
- Calibration set + reliability chart for certainty.
- Model switch per task (e.g. Opus for alignment), if Sonnet quality falls short.
- Hosted, multi-user version.

## 15. Decision log
| Question | Decision |
|---|---|
| Creative-brief matching in v1? | Yes |
| Audio: speech, sound events, or both? | Both; **sound events optional** for now |
| Tag vocabulary | Emergent (Claude chooses freely) |
| Tags grouped into categories? | Yes, emergent categories |
| Charts | One per file |
| Persistence / export | Save results; CSV + JSON export |
| Model | One model: **`claude-sonnet-5`** |
| Stack | Maximum simplicity: Python + Streamlit + SQLite |
| Alignment dimensions | Fixed: customer, context, product, style (−1…+1) |
| When alignment runs | Automatically on every file when a brief is given |
| Certainty cost (K = 3 default) | Acceptable (estimated ~$0.03–0.04/image, ~$0.15/video; measured ≈ $0.054/image, ≈ $0.066 with a brief) |
| Brief input | Paste text |
| Brief drafting helper | Yes, in v1 |
| Data-handling restrictions | None |
| Certainty explanation | Separate **tab** (not a page), with self-confidence explained (2026-09-30) |
| Header subtitle | Exact wording supplied by the user (2026-09-30) |
| Absence in brief alignment | Scores **0**, not −1 (2026-09-30) |
| Chart labels | Every bar must show its label (2026-10-01) |
| Second use: features for performance modelling | Added to the plan (2026-10-05, from the README): stable asset keys, library vocabulary, model-ready exports (§18) |
| Video support timing | Build `.mp4` support now, before Phase 4 (2026-10-05) |
| YouTube videos | No direct URL support yet; options under discussion (§17). Meanwhile, screen-record with Snipping Tool and upload the `.mp4` (works) |

## 16. Change log
| Date | Change |
|---|---|
| 2026-09-29 | Plan written. Phase 0 setup (Python 3.12.10, ffmpeg 9.0.2, venv, API key verified). Phase 1 built and tested: tagging, merging, certainty, chart, re-filtering. |
| 2026-09-30 | Phases 2–3: tabs; "How certainty works" tab explaining self-confidence; subtitle; brief drafting (≤ 250 words); brief alignment with re-evaluate; absence scores 0; 90 s API timeout; fixed garbled characters in `app.py`. |
| 2026-10-01 | Chart fix: every bar label shown (no label hiding, 30 px rows, padded axes); charts moved to `charts.py`. Plan updated to match the build. First git commit; pushed to private repo github.com/cesarbrea/content-analyzer. |
| 2026-10-05 | YouTube options discussed (§17). Phase 6 for `.mp4`: scene-based frame sampling, local transcription, video-aware prompts, frames/transcript display, ignore player chrome. Fixes: `truststore` for the corporate network, raw-audio input to faster-whisper, ffmpeg lookup. Measured video cost ≈ $0.12 with a brief. 18 tests. |
| 2026-10-05 | Added the second use from the README, creative features for performance modelling: purpose (§1), data model fields (`asset_key`, `content_hash`, `prompt_version`, `vocabulary`), model-ready exports (§10), Phase 4b, risks, and §18. |

## 17. YouTube URLs (under discussion, not planned yet)

Claude can't watch a YouTube link (web fetch sees only the page HTML), so the app has to obtain frames and audio itself and then use the Phase 6 video pipeline. Options discussed on 2026-10-05:

| | Approach | Gives | Considerations |
|---|---|---|---|
| A | Download with `yt-dlp`, then the normal video pipeline | Full analysis | YouTube's Terms of Service forbid downloading except through YouTube's own features; a policy decision for the user (and possibly AlixPartners for client work). The tool needs frequent updates |
| B | Official YouTube Data API: metadata + high-res thumbnail | Thumbnail + title/description/tags; no frames, no audio | Fully within the rules; limited |
| C | B + transcript via an unofficial library | Adds spoken content | Grey area (scraping); captions not always available |
| D | Screen recording (Snipping Tool) → upload `.mp4` | Full analysis | **Works today**, used on 2026-10-05. Manual; player controls appear in frames, which the prompt now ignores |
| E | Get the master file from the asset owner | Full analysis, best quality | Best for client creative |
| F | Gemini API for the video step (accepts public YouTube URLs) | Full analysis | Adds a second AI provider; conflicts with the one-model decision and muddies the certainty method |

**Suggested direction:** a "YouTube URL" input with a Quick mode (B + C) and an opt-in Full mode (A) with a Terms of Service note; D/E for client work.

## 18. Creative features for performance modelling (Phase 4b)

**Goal:** make every analyzed asset a row of consistent, numeric creative features that can be joined to performance data (CTR, conversions, sales lift, and so on) and used in propensity models and media mix models.

**The core tension:** tags are deliberately **emergent**: Claude picks the words, which is good for discovery. Models need **the same feature name for the same idea across all assets**. The plan keeps both, as two layers:

| Layer | What it is | Used for |
|---|---|---|
| **Tags** (per asset) | Claude's own words, merged within the asset's K runs (as now) | The per-asset chart, creative review, discovery |
| **Features** (library vocabulary) | Tags mapped to shared canonical terms across *all* saved assets | Feature matrix, modelling, cross-asset comparison |

**How the vocabulary is built:**
1. When an asset is saved, each new canonical tag is compared with the existing vocabulary in one cheap Claude call: "is this the same as an existing feature, or new?" The same rules as the within-asset merge apply (synonyms merge; broader and narrower terms stay separate).
2. Matches map to the existing feature; new ones are added. The raw tag is always kept.
3. A **Vocabulary** view lets you rename, merge, or split features, and can lock the vocabulary so further assets only map onto existing features (a stable feature set for a modelling project).
4. If the vocabulary changes, the feature matrix is rebuilt from stored tags with no new API calls.

**Feature values:** certainty (0–1), or 0 when absent; optionally binary at a threshold. Alignment scores (−1…+1 per dimension, plus overall) are included as features when a brief was used. Emergent categories (Phase 5) let you aggregate, e.g. "any people feature", "any outdoor setting".

**Reproducibility:** each value records model + prompt version. The export warns if the library mixes versions, and a **"re-run library"** action re-analyzes all assets under the current version (cost shown first).

**Out of scope here:** importing performance data and fitting the models. The app produces model-ready features; modelling happens in the user's tools (Python, R, or an MMM platform).

**Open questions (for Phase 4b):**
1. **Join key:** what identifies a creative in your performance data (platform ad ID, creative ID, filename, something else)? This decides how `asset_key` is entered: typed, read from the filename pattern, or imported from a mapping CSV.
2. **Feature encoding:** certainty values, binary, or both?
3. **Vocabulary control:** fully emergent (vocabulary grows with each asset) or a lockable feature set per project, as proposed?
4. **Scale:** roughly how many assets per modelling project? This affects cost (≈ $0.05–0.12 per asset) and whether batch processing matters.
**Open questions:** whose videos (client, competitor, own)? typical length? is the download option (A) acceptable? is a second AI provider (F) worth considering?
