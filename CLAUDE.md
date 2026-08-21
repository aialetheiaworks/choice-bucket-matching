# CHOICE Bucket Matching Engine

Root-word bucket matching pipeline for the CHOICE "Decision Intelligence
Platform" — the Intent Classifier / Pattern Matching step. Full design docs:

- `CLAUDE_CODE_BUILD_BRIEF.md` — sequenced build plan (Phases 0-6), locked
  decisions, out-of-scope items. Read this before changing pipeline logic.
- `CHOICE_Bucket_Matching_Requirements.md` — original requirements/design
  doc with the reasoning behind those decisions.

## Pick up here (paused 2026-08-22)

Deployed to Streamlit Community Cloud (confirmed by user) and Phase 5
(persistence/logging) is done. All 6 build-brief phases (0-6) are now
complete — what's left is follow-up investigation, not phased build work.

**Immediate next action:** git push today's changes (lemma fix, Phase 5
logging, 5 new eval cases + Localization synonym fix) so the live
Streamlit Cloud deploy picks them up (auto-redeploys on push to `main`).
Not yet pushed as of this update — user said push will happen later.

**2026-08-22 session, part 2 — eval set expanded to 23 cases:** added 5
cases (19-23) targeting Ethics/Privacy/Sustainability/Accessibility/
Localization, the domains the original 18 never exercised. Found:
Accessibility was fine; Localization had a real vocabulary gap (fixed —
verb-form synonyms like "translating"/"adapting" weren't matching
noun-form synonyms like "translation"/"adaptation", same lemma-mismatch
bug class as "data"/"datum"); Ethics/Privacy/Sustainability all matched
correctly but **lost their top-5 slot to other relevant buckets in the
same statement** — not a vocabulary problem, and notably this is the same
top-5-capacity pressure seen in the (reverted) taxonomy-overlap merge
attempt, but now showing up across *unrelated* bucket clusters too. Full
eval recall: 70.4% -> 71.3% after the Localization fix. Full writeup:
`PHASE6_EVAL_RESULTS.md` ("2026-08-22 follow-up #2").

**2026-08-22 session, part 3 — eval set expanded to 28 cases:** added 5
more (24-28) targeting Lessons Learned/Communication/Monitoring/
Dependencies/Quality. Found and fixed 3 real vocabulary gaps
(Communication, Monitoring, Dependencies — all zero raw match before,
all now win their top-5 slot outright after adding real business terms
their WordNet/Datamuse-built lists were missing). Recall: 63.6% -> 65.0%
on 28 cases. Full writeup: `PHASE6_EVAL_RESULTS.md` ("follow-up #3").

**Remaining untested buckets: down to 8 of 77** (`Assumptions`,
`Competition`, `Competitive Landscape`, `Constraints`, `External
Environment`, `Innovation`, `Problem Definition`, `ROI`) — converging
faster than the original per-round estimate suggested, since new cases
keep incidentally exercising buckets beyond their intended target.

**2026-08-22 session, part 4 — eval set expanded to 34 cases, coverage
goal reached:** added the last 6 cases (29-34), covering the final 8
never-tested buckets. Found and fixed 3 more real vocabulary gaps
(`External Environment` missing its own prompt's PESTLE-dimension words
like "economic"; `Assumptions` missing the verb form "assume";
`Customer Experience` missing "ux"/"user experience"). Also fixed
`Reliability` (missing "fail"/"failure," found while re-checking case 26
more carefully — see correction below). Recall: 61.8% -> 63.5% (34
cases). **Milestone: 0 of 77 buckets are now untested** — every bucket
has raw-matched at least once, reached in 4 rounds this session (faster
than the ~6-7 round estimate). Full writeup: `PHASE6_EVAL_RESULTS.md`
("follow-up #4").

**Self-correction:** follow-up #3 mischaracterized `Performance`/
`Metrics` in case 26 as a possible vocabulary gap. Re-checked raw scores
before touching them this round — they actually match fine and lose the
top-5 tie-break, same as the crowding pattern elsewhere. Lesson: always
check raw `match_buckets()` scores, not just top-5 membership, before
concluding something is a vocab gap vs. a crowding loss.

**Next step:** with coverage done, **what's left is the crowding
pattern, not more synonym tuning.** It's now shown up in **7 independent
instances across 5 unrelated bucket clusters** this session alone —
strong, repeated, no-longer-deniable evidence it's the pipeline's real
remaining weakness. This needs your decision (raise `TOP_N`? different
tie-break rule? something else?) before any more code changes here —
don't attempt another blanket fix without it, per the reverted
equivalence-merge lesson. Otherwise: push today's changes (the live
Streamlit deploy is still running yesterday's code).

## Current status (last updated: 2026-08-22)

| Phase | What | Status |
|---|---|---|
| 0 | Synonym list generation (`generate_synonyms.py`, `merge_reviewed_synonyms.py` → `bucket_library.json`) | Done, tuned once (see Phase 6) |
| 1 | NLP extraction (`extract_roots.py`) | Done. 2026-08-22: fixed a real lemma bug (see below). |
| 2 | Matching engine (`match_buckets.py`) | Done. 2026-08-22: same lemma fix applied here too. |
| 3-4 | Ranking + tooltip rendering (`get_tooltip.py`) | Done. 2026-08-22: tried and reverted an equivalence-group merge (see below). |
| 5 | Persistence & logging of match results | **Done 2026-08-22.** New `match_logger.py`, wired into `rank_buckets()` (the one chokepoint every front end already calls) so CLI/Flask/Gradio/Streamlit all log for free. Appends JSONL to `match_log.jsonl` (gitignored) — timestamp, master prompt, raw match data, zero-/low-match flags, and what was shown. Known gap: Streamlit Community Cloud's filesystem is ephemeral across redeploys, so this doesn't durably accumulate on the live deploy yet — fine for local/CLI use now, revisit with a real DB if the live deploy's history needs to survive redeploys. |
| 6 | Evaluation against labeled eval set | Run 2026-08-20 (recall 22.2% → 73.3% on 18 cases). Expanded across 3 more rounds 2026-08-22 to close every untested bucket: 23 cases (71.3%) → 28 cases (65.0%) → **34 cases, 0 of 77 buckets untested, recall 63.5%** (recall trends down as coverage widens into harder/thinner-vocab buckets, not a regression — every round's fixes were verified with no loss on prior cases). Full writeup: `PHASE6_EVAL_RESULTS.md`. |

**2026-08-22 session — two items investigated:**

1. **Fixed:** `extract_roots.py` / `match_buckets.py` — the "data"/"datum"
   lemma bug flagged in the Phase 6 writeup was real. spaCy lemmatizes
   standalone "data" to "datum" (default plural tag) but leaves it as
   "data" when it directly precedes another noun ("data strategy"), and
   the bucket-library loader lemmatized the literal synonym "data" down
   to "datum" too — so phrasing like "data strategy" or "customer data"
   silently never matched the `Data & AI` bucket. Fixed with a small
   `IRREGULAR_LEMMAS` override (forces "data" -> "data" regardless of
   spaCy's tag) in both files. Verified directly against all three
   business phrasings from the original bug report — now match. Doesn't
   move the 18-case eval's aggregate number (a `Data & AI` hit gained in
   case 11 crowded out a `Timeline` hit via tie-break), but is a real,
   confirmed fix — same pattern as the CRF join-coherence fix in the
   sibling CHOICE Forge project.
2. **Tried and reverted:** merging `Compliance`/`Governance`/`Legal` into
   `Governance & Compliance` as one equivalence-group slot (extending the
   existing same-name tier-dedup mechanism), to address the "bucket
   taxonomy overlap" flagged below. Measured effect: recall **dropped**
   73.3% → 70.0%, and it didn't even fix its target case (case 7) under
   the eval's exact-name scoring. Root cause: case 12 (an RBI-compliance
   fintech statement) expects `Compliance`, `Legal`, and `Governance` as
   three genuinely **distinct** hits, not duplicates — disproving the
   "these always overlap" assumption from the Phase 6 writeup. Reverted;
   `get_tooltip.py`'s `_dedupe_tiers` docstring has the full note. The
   taxonomy-overlap question is still open, but now with real evidence
   that a blanket merge is the wrong fix — it may need to be case-by-case
   (e.g. only merge when a statement's phrasing is generic vs. specific)
   or a genuinely different tie-break rule, not a bucket-library change.
   `Sales`/`Marketing`/`Growth Strategy` wasn't re-tested (same caution
   applies — don't assume overlap without per-case evidence first).

**Next step:** Phase 5 (persistence/logging) is the clear unblocked next
step. The taxonomy-overlap question needs more per-case evidence (ideally
more eval cases in the Compliance/Governance/Legal and Sales/Marketing/
Growth Strategy space) before attempting another fix — don't re-attempt
a blanket merge without that.

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
