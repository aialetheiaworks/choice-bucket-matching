# CHOICE Bucket Matching Engine

Root-word bucket matching pipeline for the CHOICE "Decision Intelligence
Platform" — the Intent Classifier / Pattern Matching step. Full design docs:

- `CLAUDE_CODE_BUILD_BRIEF.md` — sequenced build plan (Phases 0-6), locked
  decisions, out-of-scope items. Read this before changing pipeline logic.
- `CHOICE_Bucket_Matching_Requirements.md` — original requirements/design
  doc with the reasoning behind those decisions.

## Pick up here (paused 2026-08-20)

**Immediate next action:** the user needs to deploy `streamlit_app.py` on
Streamlit Community Cloud themselves (share.streamlit.io → sign in as
GitHub account `aialetheiaworks` → New app → repo
`aialetheiaworks/choice-bucket-matching`, branch `main`, file
`streamlit_app.py` → Deploy). This needs their own browser/OAuth login,
so it couldn't be done from here — everything up to that point (repo
created, code pushed, `requirements.txt` ready) is done. Once they've
deployed, next step is just confirming the live URL works, then decide
between Phase 5 (persistence/logging) or the bucket-taxonomy-overlap
question below.

## Current status (last updated: 2026-08-20)

| Phase | What | Status |
|---|---|---|
| 0 | Synonym list generation (`generate_synonyms.py`, `merge_reviewed_synonyms.py` → `bucket_library.json`) | Done, tuned once (see Phase 6) |
| 1 | NLP extraction (`extract_roots.py`) | Done |
| 2 | Matching engine (`match_buckets.py`) | Done |
| 3-4 | Ranking + tooltip rendering (`get_tooltip.py`) | Done |
| 5 | Persistence & logging of match results | **Not started** — no logging/saving exists in any pipeline script yet |
| 6 | Evaluation against labeled eval set | **Run 2026-08-20, two tuning rounds applied, then deliberately stopped.** Recall went 22.2% → 73.3% (avg hits/case 1.11 → 3.67 out of 5). Full writeup: `PHASE6_EVAL_RESULTS.md`. `bucket_library.json` backed up pre-edit as `bucket_library.json.bak-20260820`. |

**Next step — this needs a decision, not more synonym tuning:** the eval
run traced remaining misses down to individual tie-breaks and found the
real blocker is **bucket taxonomy overlap**, not vocabulary — several
tier-1/tier-2 buckets cover near-identical ground and split the same
signal across multiple slots instead of deduping (only same-*name*
buckets dedupe today): `Compliance` / `Governance` / `Legal` /
`Governance & Compliance`, and `Sales` / `Marketing` / `Growth Strategy`.
Decide whether to merge/rescope those, or change the tie-break rule —
see "Where this stopped, and why" in `PHASE6_EVAL_RESULTS.md`. Until
that's decided, this is a reasonable point to move on to Phase 5
(persistence/logging) instead, since more synonym tuning here has
diminishing returns. No pipeline code (`extract_roots.py`/
`match_buckets.py`) was changed in either round — only
`bucket_library.json` synonym lists.

## Working agreement — keep this file current

This file is the source of truth for where the project stands, so a
session started cold (no prior conversation) can resume correctly.

**After completing any meaningful step of work here** (finishing a phase,
running the eval, fixing a bug, making a design decision, adding a
script) — before ending the turn:

1. Update the status table above (or add rows as new phases start).
2. Update "Next step" to reflect what should happen next.
3. If a decision was made or reversed, add/update a dated line under
   "Locked decisions" below (mirror the format already used in
   `CLAUDE_CODE_BUILD_BRIEF.md`).

Don't wait to be asked — treat this as part of finishing the task, the
same way tests or a summary would be.

## Test UI (not part of the phased build — for internal testing only)

Three front ends over the same pipeline (`match_buckets` + `get_tooltip`),
all added 2026-08-20 while chasing a free way to host this live:

- `app.py` + `templates/index.html` — Flask version, local-only
  (`python3 app.py`, open `http://127.0.0.1:5000`). Was meant for Docker
  on Hugging Face Spaces, but free HF accounts can't create Docker
  Spaces (needs a verified payment method). `Dockerfile` kept around in
  case that changes.
- `gradio_app.py` — Gradio version. Also blocked on HF's free tier: as of
  2026-08-20, HF requires a *paid* plan for Gradio Spaces too — only
  Static (browser-only, no real Python) is free, which can't run spaCy.
  Kept in the repo; `README.md`'s HF Space front matter still points at
  it in case HF Pro ever happens.
- `streamlit_app.py` — **this is the one actually being deployed.**
  Streamlit Community Cloud runs a real Python backend for free from a
  GitHub repo (no payment verification), unlike HF's current tier.

**Live deploy status:** pushed to
`https://github.com/aialetheiaworks/choice-bucket-matching` (public repo,
`main` branch) on 2026-08-20. Streamlit Cloud deploy (share.streamlit.io,
pointed at `streamlit_app.py`) requires the user's own GitHub OAuth login
to Streamlit — that last click has to happen in their browser, not
something doable from here. Once deployed the app auto-redeploys on every
push to `main` (Streamlit Cloud's default behavior) — so future pipeline
or synonym-list changes just need a normal `git push`, no redeploy step.

`requirements.txt` covers all three front ends (`flask`, `gradio`,
`streamlit`, `spacy`) plus a direct pip-installable wheel URL for
`en_core_web_sm` (works with all three hosts — none of them run a
`spacy download` step, so the model has to install as a normal package).

## Locked decisions (mirrored from the build brief — check that file for full rationale)

- v1 ships synonym-list-only matching, no spaCy vector/cosine fallback.
- Single input: Choice Forge master prompt only (raw query dropped, 2026-08-19).
- Negation not suppressed/detected in v1 (2026-08-18) — focus on positive
  statements for now (2026-08-19 requirements doc note).
- Match against both tiers; dedupe overlapping bucket names to the Tier 1
  prompt (2026-08-18).
- `CORE_BUCKETS = ["Business Objective", "Customer", "Value Proposition", "Risk", "Market"]`
  — used for tie-break priority and as the zero-match fallback (2026-08-18).
- Fewer-than-5 matches: show fewer lines, don't pad with core buckets (2026-08-18).

## Explicitly out of scope for this build

- The Knowledge Graph itself (separate system, consumes this engine's output).
- spaCy semantic-vector fallback (only revisit if Phase 5 logging shows a
  real recurring coverage gap in production).
- Tier 2 framework tools (dedicated PESTLE/SWOT/etc. products).
