# CHOICE Bucket Matching Engine

Root-word bucket matching pipeline for the CHOICE "Decision Intelligence
Platform" — the Intent Classifier / Pattern Matching step. Full design docs:

- `CLAUDE_CODE_BUILD_BRIEF.md` — sequenced build plan (Phases 0-6), locked
  decisions, out-of-scope items. Read this before changing pipeline logic.
- `CHOICE_Bucket_Matching_Requirements.md` — original requirements/design
  doc with the reasoning behind those decisions.

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

Two front ends over the same pipeline, both added 2026-08-20:

- `app.py` + `templates/index.html` — Flask version, local-only. Run with
  `python3 app.py`, open `http://127.0.0.1:5000`. Was going to be
  deployed via Docker to Hugging Face Spaces, but Docker Spaces need a
  verified payment method on a free HF account — blocked, kept the
  `Dockerfile` around in case that changes later.
- `gradio_app.py` — Gradio version, same pipeline (`match_buckets` +
  `get_tooltip`), built specifically to deploy on Hugging Face Spaces'
  free tier without payment verification. This is the one `README.md`'s
  Space front matter (`sdk: gradio`, `app_file: gradio_app.py`) points
  at. Run locally with `python3 gradio_app.py`.

`requirements.txt` covers both (`flask`, `gradio`, `spacy`, plus a direct
wheel URL for `en_core_web_sm` — Gradio Spaces just run `pip install -r
requirements.txt`, there's no Docker build step to run `spacy download`
in, so the model has to be installable as a normal pip package).

This project is now a git repo (`git init` done 2026-08-20, initial
commit made) specifically so it can be pushed to a Hugging Face Space.
Not yet pushed — needs the user's own HF account/token.

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
