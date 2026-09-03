# CHOICE Bucket Matching Engine

Root-word bucket matching pipeline for the CHOICE "Decision Intelligence
Platform" — the Intent Classifier / Pattern Matching step. Full design docs:

- `CLAUDE_CODE_BUILD_BRIEF.md` — sequenced build plan (Phases 0-6), locked
  decisions, out-of-scope items. Read this before changing pipeline logic.
- `CHOICE_Bucket_Matching_Requirements.md` — original requirements/design
  doc with the reasoning behind those decisions.

## Pick up here (paused 2026-09-03)

**2026-09-03 session — near-duplicate tooltip lines fixed (display half
of the bucket-overlap question):**

A stakeholder-style test query ("I am a marketing manager, my CEO wants
me to increase the sales of our product 3x next year, our product is
B2C") returned **two lines saying the same thing** — *"Consider market
size, maturity, growth, and dynamics."* (Market, T1) and *"Assess market
size, growth potential, attractiveness, maturity, and whitespace..."*
(Market Opportunity, T2).

**Finding — structural, not a stray pair.** Pairwise prompt-text overlap
across all 80 buckets turns up **12 Tier-1 / Tier-2 twin pairs** (a T1
topic and its T2 "strategic lens" restating it): Competition/Competitive
Landscape (1.00), Market/Market Opportunity (0.80), Revenue/Pricing &
Monetization, Legal/Governance & Compliance, Customer/Customer Needs
(0.75), then a tail at 0.5-0.6. Full table: `PHASE6_EVAL_RESULTS.md`
follow-up #8.

**Fixed (display half): `get_tooltip.DEDUP_SIMILAR_PROMPTS = True`**
(threshold `PROMPT_OVERLAP_THRESHOLD = 0.75`). In `rank_buckets()`, after
the sort and *before* the TOP_N/MAX_N cut, drop any bucket whose prompt
near-duplicates a higher-ranked kept bucket's (overlap coefficient on
content words). Higher-ranked twin kept; T1 sorts ahead of its T2 twin so
the T1 prompt wins, consistent with `_dedupe_tiers`. Freed slot goes to a
real bucket. New helpers `_prompt_content_words()` /
`_near_duplicate_prompt()` / `_dedupe_similar_prompts()`. `dedup` param
added to `rank_buckets()` for the harness. `eval_harness.py` gains a
`count_salience_dedup` config. `bucket_library.json` **not touched**.

**Eval:** vs the live `count_salience` default — full-list 77.1% → 76.5%,
top-5 62.4% → 61.8% (−1 hit each, noise; the metric scores exact bucket
*names* but dedup is about guidance *text*, so it understates the fix).
3 cases moved: case 12 **+1** (dropped the redundant "Governance &
Compliance" T2 umbrella, freed a slot for Timeline — and Compliance/
Legal/Governance all stayed distinct, so the 2026-08-22 reverted-merge
landmine held); case 13 −1 (Revenue → Pricing & Monetization, borderline);
case 29 −1 (labeler wanted both Competition + Competitive Landscape, but
their prompts overlap 1.00 so showing both *is* the redundancy). On the
reported query: Market Opportunity drops, Go-to-Market takes the freed
slot, no repeated guidance.

**The library half is still open — stakeholder call.** Take the twin-pair
table to them: should the ~12 Tier-2 twins be (a) rewritten to a
genuinely distinct strategic-lens angle, (b) merged into their T1 twin,
or (c) left for the engine to dedupe at display time (current)? Also
worth asking: should the tooltip show Tier-2 buckets at all, or is Tier 2
a separate feature (strategic framing / the downstream Knowledge Graph)?

**Pushed + verified live 2026-09-03** (`e75dde8` on `main`): hit the
reported query against production — "Market Opportunity" is gone, the
redundant "Assess market size, growth potential..." line no longer shows,
Go-to-Market took the freed slot. Toggle back with
`DEDUP_SIMILAR_PROMPTS = False`.

---

**2026-09-02 session — dependency-salience scoring added from a
stakeholder sample script:**

The stakeholder shared `~/Downloads/concept_scoring_sample.pdf` — a
standalone spaCy dependency-parse concept weighter (no LLM): walk each
matched concept's token up to its sentence ROOT, score `1/(hops+1)` so a
concept that *is* the main verb counts ~1.0 and one buried deep in a
subordinate clause counts a fraction of that. Adapted into the pipeline
as an **optional scoring signal, wired as a tiebreak** (not a replacement
for the count-based score).

1. **`extract_roots.extract_roots_salience()`** — same roots as
   `extract_roots()`, each mapped to its salience weight (min hop-distance
   across occurrences → `1/(hops+1)`; phrases use their shallowest
   token). `set(extract_roots_salience(x)) == extract_roots(x)` always.
2. **`match_buckets.py` computes both scores on one parse:** `count_score`
   (distinct matched terms — the original) and `salience_score` (summed
   salience weights of those terms). `SCORING_MODE` (default `"count"`)
   picks the primary `score` field; both always travel on every result.
3. **`get_tooltip.RANK_MODE`** (default `"count_salience"`) picks ranking
   order: `count` (original), `salience` (pure), or `count_salience`
   (rank by count, break ties by salience, then core priority, then
   name).
4. **`eval_harness.py` committed** — was always a throwaway scratch
   script re-written each session. `python3 eval_harness.py --compare
   --verbose` runs all three configs with a per-case diff.
5. **`api.py`** `RankedBucket` now also exposes `count_score` /
   `salience_score` (additive, optional — no breaking change).

**Eval (34 cases):** `count` (old default) full-list recall 78.2%, top-5
60.0%, avg 8.15 lines. **`count_salience` (new default):** full-list
77.1% (−2 hits, within tie-shift noise), **top-5 62.4% (+4 hits)** — the
salience tiebreak pulls syntactically-central buckets *up* into the first
5 lines. Pure `salience`: full-list 62.9% (bad — collapses the boundary
tie groups that positions 6-9 recall depends on), but shorter (5.91
lines) and higher precision (54.3%) — kept as a documented option if
priorities ever shift to brevity. Full writeup: `PHASE6_EVAL_RESULTS.md`
follow-up #7.

**This also answers the reduce/improve precision question** left open on
2026-09-01: a bucket triggered only by a bare generic verb in a
subordinate clause now scores a low salience weight and loses contested
slots — no vocabulary edit needed. That open item is now resolved.

`bucket_library.json` / `bucket_index_cache.pkl` unchanged (lemmatization
logic untouched; `CACHE_VERSION` stays 2).

**Committed + pushed 2026-09-02** (`b963d03` on `main`) after the user
reviewed the eval numbers and a live example — Render + Streamlit Cloud
auto-redeploy from `main`. **Deploy verified live 2026-09-02:** Render
redeployed, `/health` 200 (32.6s cold start, normal baseline), `/tooltip`
now returns the `count_score`/`salience_score` fields and the
`count_salience` ranking is active in production (spot-checked the
"marketing manager / CEO wants" example — `Customer Needs` at salience
1.0 correctly ranked ahead of the salience-0.5 buckets in its count-tier,
matching local). Nothing outstanding. To revert the ranking behavior
without a full rollback: set `RANK_MODE = "count"` in `get_tooltip.py`
and push.

## Pick up here (paused 2026-09-01)

**2026-09-01 session — stakeholder feedback round: tooltip format
shortened, chunk-priority matching built:**

1. **Tooltip format shortened.** Stakeholder feedback: drop the "If you
   are speaking about X, also consider thinking about →" wrapper — the
   tooltip line is now just the bucket's prompt text directly (e.g.
   "Consider market size, maturity, growth, and dynamics."). `get_tooltip.py`'s
   `render_tooltip()` now returns `r["prompt"]` directly; the `TEMPLATE`
   constant is gone. `API_DOCUMENTATION.md` updated to match.
2. **Chunk-priority phrase matching built** (stakeholder feedback + a
   real bug found in the process): when a longer known vocabulary phrase
   matches (e.g. "go to market"), its constituent single words ("market",
   "go") should no longer separately trigger other buckets — previously
   they always did, since phrase extraction and single-word extraction
   ran independently with no suppression between them.
   - **Bug found:** spaCy's `en_core_web_sm` flags "go" as a stopword on
     *every* occurrence (a static lexeme property, not context-dependent
     — verified directly). That silently collapsed "go to market" and
     "go-to-market" down to just "market" everywhere in the vocabulary,
     making the dedicated Go-to-Market bucket's own synonym
     indistinguishable from the generic Market bucket. Fixed with a
     `NEVER_STOP = {"go"}` override in `extract_roots.py`, applied on
     both the vocabulary-lemmatization side (`match_buckets.py`'s
     `_lemmatize_term`) and the input side.
   - **Architecture change:** `extract_roots()` (Phase 1) replaced its
     noun-chunk-based phrase guessing (which only caught noun-phrase-shaped
     text — never idioms like "go to market", a verb phrase) with
     vocabulary-driven longest-match scanning: `match_buckets()` now
     builds the set of every known multi-word bucket vocabulary phrase
     and hands it to `extract_roots(master_prompt, phrase_vocab=...)`,
     which scans the prompt for those exact phrases (longest first) and
     marks matched positions as consumed so they can't also surface as
     separate single-word roots. 67% of the vocabulary (6,442 of 9,555
     synonyms) is multi-word, so this touches most of the matching
     surface, not an edge case.
   - **`bucket_index_cache.pkl` regenerated and `CACHE_VERSION` bumped
     1 → 2** (the lemmatization logic changed, not just the vocabulary
     file — the version bump is what forces every deployed instance to
     rebuild instead of silently serving the stale pre-fix cache).
   - **Eval impact, and the follow-on decision it forced:** at the
     existing `MAX_N=7` crowding cap, recall on the 34-case eval *dropped*
     75.9% → 71.8% — not because the phrase logic is wrong (verified
     directly against the "go to market" example and several others,
     works exactly as intended), but because suppressing redundant
     sub-word matches removes "noise" scores that used to let some
     buckets win clean top slots, pushing more buckets into score ties
     and hitting the existing cap harder. Measured the cap directly:
     `MAX_N=9` → 78.2%, `MAX_N=12` → 81.8% (ceiling — no case's tied
     group exceeds 12; uncapped gives the same number). **User's decision:
     raised `MAX_N` 7 → 9** — clears the pre-fix baseline (78.2% >
     75.9%) while keeping the tooltip list closer to its original length
     than 12 would (typical statements now show close to 9 lines, up
     from 5-7 — a real, accepted UX tradeoff, not a bug). Full reasoning
     in `get_tooltip.py`'s module docstring.
3. **Reduce/improve ambiguity investigated** (stakeholder question: these
   verbs could imply either a business or technical meaning). Cross-checked
   against the stakeholder-supplied `Business Root Vocabulary 2.1.docx`
   (their own source doc): it places `reduce`/`improve` under exactly the
   same buckets we already have (Business Objective / Continuous
   Improvement) — no technical bucket (Performance, Reliability, Technology,
   etc.) uses either bare word as a synonym anywhere in the doc; those
   buckets instead use specific compound terms ("performance degradation",
   "performance gain", etc.). So this isn't a wrong-bucket-assignment
   problem fixable by editing the vocabulary — the doc's own authors
   already avoided attaching generic verbs to technical buckets. **Not
   yet resolved** — reported back to the user as a precision/confidence
   question (should single generic-verb-only matches be treated as
   weaker signals than they currently are?), not something to fix
   unilaterally. Open for next session.

**Next step:** pushed and confirmed live 2026-09-01 — Render redeployed
from `main` (`4bb781d`), spot-checked `/health` (32.6s cold start, in
line with the earlier fix) and `/tooltip` with the "go to market"
example directly against production: correctly returns Go-to-Market +
Marketing, no diluted separate Market hit, shortened tooltip format
confirmed live too. Nothing outstanding on deploy. Remaining open item
for next session: the reduce/improve precision question (item 3 above)
— still needs the user's call, not resolved yet. **[Resolved 2026-09-02
by the dependency-salience tiebreak — see the top "Pick up here".]**

**2026-08-29 → 2026-08-31 session — API service built, deployed, and a
real cold-start bug found and fixed:**

1. Built `api.py` (FastAPI): `POST /tooltip` + `GET /health`, loading the
   bucket index once at startup rather than per-request. `requirements-api.txt`
   added as a lean, deploy-only dependency set (`fastapi`/`uvicorn`/`spacy`
   only) — the original `requirements.txt` bundles `flask`/`gradio`/
   `streamlit` too, and `fastapi` and `gradio` have an unresolvable
   `starlette` version conflict when installed together. `Dockerfile`
   repointed at `api.py`/uvicorn (was serving the old Flask test UI).
2. Deployed to **Render** (free web service tier, no card required —
   same reasoning as the Streamlit Cloud choice). Live at
   `https://choice-bucket-matching.onrender.com`. Language must be set to
   **Python 3** explicitly on Render, not the auto-detected Docker (the
   Docker path is unverified — no local Docker install to test it
   against).
3. **Found via load-testing the live deploy:** cold start (first request
   after Render's free-tier ~15min idle spin-down) took **292.6 seconds**
   — confirmed by direct measurement, not estimated. Root cause: the
   long-flagged `load_bucket_index()` cost (~14s locally, per the
   2026-08-25 vocabulary-merge note below) scales far worse on Render's
   0.1 CPU free instance, because it re-lemmatizes all ~8,210 vocabulary
   terms through spaCy on every process boot.
4. **Fixed:** `load_bucket_index()` (`match_buckets.py`) now caches its
   output to `bucket_index_cache.pkl`, keyed by a hash of
   `bucket_library.json` + a `CACHE_VERSION` constant. Cache hit = a
   pickle load (~0.8s), cache miss = old behavior (rebuild + re-save).
   Verified the cached and freshly-built bucket index are byte-identical
   (pure caching layer, zero logic change, so no eval re-run needed).
   Local timing: 14.2s → 0.84s. CLI (`get_tooltip.py`) runtime also
   dropped ~14s → ~1s as a side effect — this was the *other* long-flagged
   issue from the 2026-08-25 vocabulary merge, fixed for free by the same
   change. **`bucket_index_cache.pkl` is committed to the repo** (not
   gitignored) so it ships pre-built in the deployed container — the
   Render cold start should no longer pay the lemmatization cost at all,
   only a fast pickle load. **Verified live 2026-08-31:** cold start
   dropped from 292.6s to 33.1s (Render's normal free-tier container
   spin-up baseline, not the vocabulary rebuild — that cost is gone).
   Warm requests: ~0.4s.
5. **Maintenance note for future sessions:** if `bucket_library.json`
   changes again, `bucket_index_cache.pkl` must be regenerated (just call
   `load_bucket_index()` once) and **committed** — the hash check will
   correctly detect the mismatch and fall back to a fresh rebuild
   automatically so nothing breaks, but that reintroduces the ~5-minute
   Render cold start silently (fast locally, slow only on Render) until
   the cache is regenerated and pushed.
6. Wrote `API_DOCUMENTATION.md` — endpoint reference for whoever
   integrates the frontend, meant to be handed to another chat/session.

**Next step:** cold-start fix confirmed live and working — nothing
blocking left on the API itself. CORS is still open (`*`) and there's no
auth; both fine for now but flagged in `API_DOCUMENTATION.md`'s
"Operational notes" for whenever this stops being local/internal testing
only. Otherwise: ready to hand `API_DOCUMENTATION.md` + the live URL to
whoever builds the Choice Forge frontend integration.

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

## Current status (last updated: 2026-09-03)

| Phase | What | Status |
|---|---|---|
| 0 | Synonym list generation (`generate_synonyms.py`, `merge_reviewed_synonyms.py` → `bucket_library.json`) | Done, tuned once (see Phase 6). **2026-08-25: merged a stakeholder-supplied vocabulary expansion** (`Business_Root_Vocabulary_2.docx`, 10,111 words) — union merge, 970 → 8,210 lemmatized terms. See below and `PHASE6_EVAL_RESULTS.md` ("follow-up #6"). |
| 1 | NLP extraction (`extract_roots.py`) | Done. 2026-08-22: fixed a real lemma bug (see below). 2026-09-01: replaced noun-chunk phrase guessing with vocabulary-driven longest-match phrase scanning + sub-word suppression, and fixed a spaCy stopword bug that silently broke "go to market" matching. **2026-09-02: added `extract_roots_salience()`** — same roots, each with a dependency-parse salience weight (`1/(hops-to-ROOT + 1)`). See "Pick up here" above. |
| 2 | Matching engine (`match_buckets.py`) | Done. 2026-08-22: same lemma fix. 2026-09-01: `load_bucket_index()` caches to `bucket_index_cache.pkl`; `match_buckets()` builds the phrase vocabulary for Phase 1. **2026-09-02: every result now carries both `count_score` and `salience_score`** (one parse); `SCORING_MODE` (default `"count"`) picks the primary. |
| 3-4 | Ranking + tooltip rendering (`get_tooltip.py`) | Done. 2026-08-22: tried and reverted an equivalence-group merge (see below). 2026-08-25: fixed the top-5 crowding pattern — tied 5th-place group extends past 5, capped at `MAX_N`. 2026-09-01: `MAX_N` raised 7 → 9; dropped the "If you are speaking about X..." wrapper. 2026-09-02: added `RANK_MODE` (default `"count_salience"`) — rank by count, break ties by dependency salience; top-5 recall 60.0% → 62.4%. **2026-09-03: added `DEDUP_SIMILAR_PROMPTS` (default on)** — drop a bucket whose prompt near-duplicates a higher-ranked one's (12 T1/T2 twin pairs, e.g. Market / Market Opportunity); library untouched, stakeholder call on merging. See "Pick up here" + `PHASE6_EVAL_RESULTS.md` follow-ups #7-8. |
| 5 | Persistence & logging of match results | **Done 2026-08-22.** New `match_logger.py`, wired into `rank_buckets()` (the one chokepoint every front end already calls) so CLI/Flask/Gradio/Streamlit all log for free. Appends JSONL to `match_log.jsonl` (gitignored) — timestamp, master prompt, raw match data, zero-/low-match flags, and what was shown. Known gap: Streamlit Community Cloud's filesystem is ephemeral across redeploys, so this doesn't durably accumulate on the live deploy yet — fine for local/CLI use now, revisit with a real DB if the live deploy's history needs to survive redeploys. |
| 6 | Evaluation against labeled eval set | Run 2026-08-20 (recall 22.2% → 73.3% on 18 cases). Expanded across 3 rounds 2026-08-22 to 34 cases, 0 of 77 buckets untested. 2026-08-25: crowding fix + vocabulary merge → 75.9%. 2026-09-01 phrase fix + `MAX_N=9` → 78.2% full-list. **2026-09-02: `eval_harness.py` committed** (was a scratch script); `count_salience` ranking → full-list 77.1%, top-5 62.4% (from 60.0%). Full writeup: `PHASE6_EVAL_RESULTS.md` follow-up #7. |

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
- Score-tie ordering (2026-09-02): the tie-break rejected in 2026-08-25 as
  having "no principled loser" now has one — **dependency-parse salience**.
  When buckets tie on matched-term count, the one whose match sits closer
  to its sentence's ROOT (more syntactically central to what the author
  said) wins the slot, ahead of the old core-priority/alphabetical rule.
  `get_tooltip.RANK_MODE = "count_salience"`. Count stays the primary
  score (pure-salience scoring measured a ~15pt full-list recall drop);
  salience is tiebreak-only. Adapted from a stakeholder sample script
  (`concept_scoring_sample.pdf`). See `PHASE6_EVAL_RESULTS.md` follow-up
  #7. Confirmed by the user and deployed live 2026-09-02.
- Near-duplicate tooltip lines (2026-09-03): ~12 Tier-1/Tier-2 bucket
  pairs have near-identical prompt text (Competition/Competitive
  Landscape, Market/Market Opportunity, Customer/Customer Needs, ...).
  **Display-time fix:** `get_tooltip.DEDUP_SIMILAR_PROMPTS` drops the
  lower-ranked twin when both would show (prompt-overlap ≥ 0.75). Chosen
  over editing `bucket_library.json` — merging the twins or rewriting the
  Tier-2 prompts is a taxonomy decision the stakeholders own (they
  supplied the 80-bucket taxonomy). This is the safe, reversible half;
  the library half is an open question for them. Eval-neutral (−1 hit,
  noise). See `PHASE6_EVAL_RESULTS.md` follow-up #8.

## Explicitly out of scope for this build

- The Knowledge Graph itself (separate system, consumes this engine's output).
- spaCy semantic-vector fallback (only revisit if Phase 5 logging shows a
  real recurring coverage gap in production).
- Tier 2 framework tools (dedicated PESTLE/SWOT/etc. products).
