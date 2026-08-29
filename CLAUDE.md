# CHOICE Bucket Matching Engine

Root-word bucket matching pipeline for the CHOICE "Decision Intelligence
Platform" — the Intent Classifier / Pattern Matching step. Full design docs:

- `CLAUDE_CODE_BUILD_BRIEF.md` — sequenced build plan (Phases 0-6), locked
  decisions, out-of-scope items. Read this before changing pipeline logic.
- `CHOICE_Bucket_Matching_Requirements.md` — original requirements/design
  doc with the reasoning behind those decisions.

## Pick up here (paused 2026-08-25)

Deployed to Streamlit Community Cloud (confirmed by user), all 6
build-brief phases (0-6) are complete, the top-5 crowding pattern
flagged throughout the 2026-08-22 session is fixed, and a stakeholder-
supplied vocabulary expansion has been merged into `bucket_library.json`.

**Update 2026-08-29:** everything below was already committed and
pushed as of this check — working tree clean, `main` matches
`origin/main` at `8a1bdcd` (the vocabulary merge commit). No push was
actually pending; the "immediate next action" note below was stale.

**2026-08-25 session, part 1 — crowding fixed, pushed live:** the
2026-08-22 session's changes (lemma fix, Phase 5 logging, 34-case eval
set) were pushed to `main` (was pending user confirmation before). Then,
the "crowding" pattern flagged repeatedly below (a bucket matches
correctly but loses its top-5 slot purely on slot count, not relevance —
7 instances, 5 unrelated bucket clusters) was fixed: `get_tooltip.py`'s
`rank_buckets()` no longer cuts at a flat top-5. If the 5th-place bucket
is tied on score with buckets beyond it, the whole tied group is now
included, capped at `MAX_N = 7`. A different tie-break *order* (raise
priority of X over Y) was considered and rejected first — checked
against the eval evidence, the losing buckets are genuinely relevant,
not noise, so no ordering rule could correctly pick one to drop; only
adding capacity helps. This is a strict extension of the old top-5 rule
(old top-5 ⊆ new result), so it's regression-free by construction —
verified 0 regressions across all 34 eval cases. Full-eval recall:
63.5% → 74.7%. Full design writeup + cap-value comparison (6 vs 7 vs 8):
`PHASE6_EVAL_RESULTS.md` ("2026-08-25 follow-up #5"). Pushed to `main`.

**2026-08-25 session, part 2 — stakeholder vocabulary merged:**
stakeholders supplied `Business_Root_Vocabulary_2.docx`, a 10,111-word
expansion of the same 80-bucket taxonomy (verified accurate against its
own stated counts) with a per-root-term "Knowledge Prompt" column that
doesn't map onto the current one-prompt-per-bucket tooltip architecture
(left unused, out of scope). Checked it against every wrong-sense/
over-triggering bug Phase 6 round 1 had already found and fixed
(Governance, Data & AI, Change Management) — clean on all three, and no
reappearance of the old flat "customer"/"client"-everywhere pollution.
Merged as a union (backup: `bucket_library.json.bak-20260825`) — every
current synonym kept (incl. the two hand-additions the new doc lacked,
`RBI`/`SOC 2`), 8,361 net-new entries added, vocabulary grew ~8.5x (970
→ 8,210 lemmatized terms). Re-ran the 34-case eval: recall 74.7% →
75.9%, net +2 hits but not regression-free this time — 8 cases improved,
5 regressed by one bucket each. Traced the regression mechanism directly
(not guessed): it's the *same* crowding pattern from part 1, recurring
one level down — more vocabulary means the score=1 tier at the ranking
boundary now sometimes exceeds 7 members, so `MAX_N=7` itself becomes a
hard cutoff that can land mid-tie. Not re-tuned here (5 cases isn't
enough evidence to pick a new cap, and net effect is still positive).
Also found: `load_bucket_index()` now takes ~14s (was near-instant) —
fine for the three front ends (all cache it at startup) but the CLI
reloads it fresh every run, so a single `get_tooltip.py` invocation now
takes ~14s. Neither the cap question nor the CLI load time was acted on
— both flagged for a future session if they cause real friction. Full
writeup: `PHASE6_EVAL_RESULTS.md` ("2026-08-25 follow-up #6"). **Not yet
pushed.**

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

## Current status (last updated: 2026-08-25)

| Phase | What | Status |
|---|---|---|
| 0 | Synonym list generation (`generate_synonyms.py`, `merge_reviewed_synonyms.py` → `bucket_library.json`) | Done, tuned once (see Phase 6). **2026-08-25: merged a stakeholder-supplied vocabulary expansion** (`Business_Root_Vocabulary_2.docx`, 10,111 words) — union merge, 970 → 8,210 lemmatized terms. See below and `PHASE6_EVAL_RESULTS.md` ("follow-up #6"). |
| 1 | NLP extraction (`extract_roots.py`) | Done. 2026-08-22: fixed a real lemma bug (see below). |
| 2 | Matching engine (`match_buckets.py`) | Done. 2026-08-22: same lemma fix applied here too. |
| 3-4 | Ranking + tooltip rendering (`get_tooltip.py`) | Done. 2026-08-22: tried and reverted an equivalence-group merge (see below). **2026-08-25: fixed the top-5 crowding pattern** — `rank_buckets()` now lets a tied 5th-place group extend past 5, capped at `MAX_N = 7`, instead of an arbitrary flat cut. See below and `PHASE6_EVAL_RESULTS.md` ("follow-up #5"). |
| 5 | Persistence & logging of match results | **Done 2026-08-22.** New `match_logger.py`, wired into `rank_buckets()` (the one chokepoint every front end already calls) so CLI/Flask/Gradio/Streamlit all log for free. Appends JSONL to `match_log.jsonl` (gitignored) — timestamp, master prompt, raw match data, zero-/low-match flags, and what was shown. Known gap: Streamlit Community Cloud's filesystem is ephemeral across redeploys, so this doesn't durably accumulate on the live deploy yet — fine for local/CLI use now, revisit with a real DB if the live deploy's history needs to survive redeploys. |
| 6 | Evaluation against labeled eval set | Run 2026-08-20 (recall 22.2% → 73.3% on 18 cases). Expanded across 3 more rounds 2026-08-22 to close every untested bucket: 23 cases (71.3%) → 28 cases (65.0%) → 34 cases, 0 of 77 buckets untested, recall 63.5%. **2026-08-25: crowding fix raised recall to 74.7%**, then the vocabulary merge raised it again to **75.9%** (34 cases; 5 cases regressed by one bucket each on the merge, 8 improved — see below). Full writeup: `PHASE6_EVAL_RESULTS.md`. |

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

**Historical note:** at the time this paragraph was written (2026-08-22),
Phase 5 and the crowding fix were both still open. Both are done now —
see "Pick up here" at the top of this file for current status. The
Compliance/Governance/Legal taxonomy-overlap question itself was
resolved as "not actually overlap" by the 2026-08-25 crowding fix (all
three are genuinely distinct hits competing for slots, not duplicates —
see `PHASE6_EVAL_RESULTS.md` follow-up #5); `Sales`/`Marketing`/`Growth
Strategy` still hasn't been specifically re-tested, but is lower-priority
now that the general slot-capacity constraint behind most of these
symptoms has been addressed.

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
- 5+ matches, ties at the boundary (2026-08-25): don't cut a tied 5th-place
  group with the existing core/alphabetical tie-break — extend the result
  to include the whole tied group, capped at `MAX_N = 7`. Chosen over
  reordering the tie-break itself (rejected — the buckets losing slots are
  genuinely relevant, not noise, so no ordering rule has a principled
  "loser" to pick) and over a flat `TOP_N` raise (cap 8 measured best
  recall but nearly always maxes out in practice; cap 7 was the balance
  point). See `PHASE6_EVAL_RESULTS.md` follow-up #5.

## Explicitly out of scope for this build

- The Knowledge Graph itself (separate system, consumes this engine's output).
- spaCy semantic-vector fallback (only revisit if Phase 5 logging shows a
  real recurring coverage gap in production).
- Tier 2 framework tools (dedicated PESTLE/SWOT/etc. products).
