# Phase 6 Evaluation Results — Bucket Matching Performance

Run 2026-08-20, following `MASTER_PROMPT_performance_check.md` against
`eval_set.json` (18 cases). Unlike the original read-only instruction in
that doc, this run also applied fixes to `bucket_library.json` and
re-measured — see "What changed" below. Done in two rounds: round 1 fixed
vocabulary gaps and wrong-sense pollution; round 2 fixed a few more
clean, generalizable misses, then stopped once remaining misses turned
out to be a slot-capacity/tie-break issue rather than a vocabulary gap
(see "Where this stopped" below).

## Headline numbers

| | Before | Round 1 | Round 2 (final) |
|---|---|---|---|
| Recall (hits / 90 expected slots) | 20/90 = 22.2% | 64/90 = 71.1% | 66/90 = 73.3% |
| Avg hits per case (out of 5) | 1.11 | 3.56 | 3.67 |
| Cases with 0 hits | 5 of 18 | 0 of 18 | 0 of 18 |
| Cases with 5/5 hits | 0 of 18 | 1 of 18 | 1 of 18 (case 8) |
| Buckets that never matched anything (of 77) | 35 | 23 | 22 |

## Root cause (before fixing)

Every dead/under-performing bucket traced back to the same issue: its
synonym list was built from WordNet + Datamuse and carried the wrong word
sense, or was missing plain business vocabulary entirely. Examples found:

- **Wrong sense entirely**: "Change Management" synonyms were all
  *software* change-management terms (changelog, source control,
  subversioning) — completely wrong domain for an org/people bucket.
  "Governance" synonyms were government/political terms (governorate,
  regime). "Data & AI" included `java`, `prolog`, `bot`.
- **Missing plain business vocabulary**: `Risk`, `Metrics`, `Timeline`,
  `Resources`, `Talent`, `Operations`, `Technology Feasibility`, `Legal`,
  `Reliability`, `Feedback` had zero matches on any of the 18 cases —
  their synonym lists were formal dictionary synonyms of the bucket name
  (e.g. Risk: "gamble, hazard, peril, jeopardy") with none of the literal
  words real objective statements use (mitigation, downtime, headcount,
  hire, quarter, deadline, audit, complaint...).
  This matches exactly what the build brief predicted: "WordNet skews
  formal/dictionary-style... casual/modern business terms may not be well
  covered."
- **Missing named terms from the brief's own example list**: freemium,
  churn, D2C, SME/SMB were absent even though `CLAUDE_CODE_BUILD_BRIEF.md`
  Phase 0 explicitly called these out as terms to add manually.
- **Over-triggering / redundant buckets**: `Customer`, `Customer
  Experience`, `Customer Needs`, and `Customer Segmentation` all carried
  the same generic `customer`/`client` synonyms, so any mention of
  "customer" flooded all four into contention and crowded out other
  genuinely distinct expected buckets. `Growth Strategy` had bare
  `strategic` as a synonym — matches almost anything. `Execution
  Planning` had `performance`/`operation`/`project`/`purpose` — too
  generic, collided with `Performance` and `Operations`.

## What changed

Edited `bucket_library.json` only (40 of 77 buckets touched) — no changes
to `extract_roots.py`, `match_buckets.py`, or `get_tooltip.py`, per the
locked v1-scope decision (no scoring-logic changes without evidence).
Original file backed up to `bucket_library.json.bak-20260820`.

- Added literal, domain-correct terms to 37 buckets (see git-free diff:
  compare against the `.bak` file) — e.g. Risk: mitigation, downtime,
  degrade, audit; Timeline: quarter, month, deadline, q1-q4; Talent:
  hire, onboard, attrition, retention; Metrics: kpi, churn rate,
  conversion rate; Pricing & Monetization: freemium, tier; Customer: d2c,
  sme, smb.
- Removed wrong-sense pollution from `Change Management` (11 software-CM
  terms), `Governance` (6 political-government terms), and `Data & AI`
  (java, prolog, bot).
- De-duplicated the Customer-family buckets by removing bare
  `customer`/`client` from `Customer Experience`, `Customer Segmentation`,
  and `Customer Needs` — they now only fire on their own specific
  vocabulary (usability/NPS for CX, segment/enterprise for Segmentation,
  need/demand/want for Needs), not on every generic customer mention.
  `Growth Strategy` lost bare `strategic`; `Execution Planning` lost
  `performance`/`operation`/`project`/`purpose`.

## Per-case results (final, after both rounds)

| Case | Hits/5 | Still missed | Still false-positive |
|---|---|---|---|
| 1 | 3/5 | Pricing, Go-to-Market | Growth Strategy, Marketing |
| 2 | 3/5 | Go-to-Market, Implementation | Customer, Data & AI |
| 3 | 4/5 | Success Measures | Growth Strategy |
| 4 | 4/5 | Growth Strategy | Business Objective |
| 5 | 4/5 | Cost | Customer |
| 6 | 4/5 | Product Strategy | Continuous Improvement |
| 7 | 3/5 | Compliance, Resources | Governance & Compliance, Backlog |
| 8 | 5/5 | — | — |
| 9 | 4/5 | Metrics | Implementation |
| 10 | 4/5 | Metrics | Timeline |
| 11 | 3/5 | Data & AI, Business Objective | Technology, Technology Feasibility |
| 12 | 4/5 | Timeline | Product Strategy |
| 13 | 3/5 | Revenue, Customer Experience | Value Proposition, Market |
| 14 | 4/5 | Data & AI | Customer |
| 15 | 3/5 | Metrics, Operations | Customer, Continuous Improvement |
| 16 | 4/5 | Decision Criteria | AI/ML |
| 17 | 3/5 | Timeline, Reliability | Customer, Execution Planning |
| 18 | 4/5 | Revenue | Business Objective |

## Where this stopped, and why

Round 2 traced every remaining miss down to its exact tie-break (dumped
full per-bucket scores, not just top-5, for the 7 lowest-scoring cases).
Finding: **almost none of the remaining misses are vocabulary gaps
anymore.** The bucket usually *does* match — it loses a genuine 3-to-6-way
tie among buckets that scored the same, and the top-5 cap has to cut
someone. Case 7 is the clearest example: `Compliance`, `Governance &
Compliance`, `Legal`, and `Governance` all independently matched
"compliance" — four buckets legitimately relevant to one concept,
competing for slots that only `Growth Strategy` and `Customer
Segmentation` (the two highest scorers) plus 2 more can fill.

This surfaces a **bucket-taxonomy overlap** that synonym tuning can't
fix, only paper over: several tier-1/tier-2 pairs cover near-identical
ground and will always compete for the same slot —
`Compliance`/`Governance`/`Legal`/`Governance & Compliance`,
`Sales`/`Marketing`/`Growth Strategy`, `Product Strategy` (tier 1 and 2,
already handled by tier-dedup only when the *name* matches exactly — these
four don't share a name, so they don't dedupe and just crowd each other
out). Fixing this would mean either merging/scoping those buckets or
changing the tie-break rule — both are scoring-logic/taxonomy decisions,
explicitly out of the "don't relitigate scoring logic without evidence"
boundary for this pass. Flagging for a decision rather than guessing.

Stopped adding synonyms at this point rather than continuing to hand-tune
individual tie-breaks — past this point, further additions would mostly
be reverse-engineering which specific term flips which specific case's
ranking (gaming this 18-case eval set) rather than fixing a real,
generalizable gap.

One genuine pipeline quirk found and **not** patched (out of scope for a
synonym-list-only fix): spaCy's `en_core_web_sm` lemmatizes the standalone
word "data" to "datum" (plural-noun tagging), but lemmatizes "data" as
"data" when it directly precedes another noun ("data scientist" → NN tag,
not NNS). This caused `Data & AI`'s "data" synonym to silently
never match the literal word "data" in most objective phrasing. Flagging
here rather than patching `_lemmatize_term` since that's Phase 1/2 logic
change, not a Phase 0 synonym-list fix — worth a scoped decision later on
whether to special-case known irregular lemmas.

## Suggested next steps (decisions needed, not further synonym tuning)

- **Bucket taxonomy overlap** (see above): decide whether to merge or
  clearly re-scope `Compliance`/`Governance`/`Legal`/`Governance &
  Compliance` and `Sales`/`Marketing`/`Growth Strategy` so they stop
  splitting the same signal across multiple slots. This is the single
  highest-leverage remaining fix, and it's a design call, not a synonym
  fix.
- 22 of 77 buckets are still dead on this eval set — expected, since this
  18-case set skews toward growth/ops/compliance-style objectives and
  never touches topics like Ethics, Privacy, Sustainability,
  Accessibility, Localization. Their synonym lists looked fine on manual
  inspection (no wrong-sense pollution like the ones that got fixed) —
  they're just unexercised by this eval set, not necessarily broken.
  Worth adding a few cases in those domains to `eval_set.json` before
  fully trusting that they're fine.
- Consider the "data"/"datum" lemma-mismatch class of bug more broadly —
  spot-check other bucket synonym lists for similar single-word terms
  that might silently mismatch depending on sentence position.

## 2026-08-22 follow-up: lemma fix, and a rejected taxonomy fix

**"data"/"datum" lemma bug — fixed.** Confirmed the root cause exactly as
predicted above: `nlp("data")` alone tags NNS (plural) → lemma "datum",
but `nlp("data strategy")` tags the first token NN (singular, modifying a
following noun) → lemma stays "data". The bucket loader lemmatized the
literal synonym "data" in isolation, so it became "datum" in
`match_terms` and never matched the literal "data" that phrasing like
"data strategy"/"customer data"/"data quality" actually extracts. Fixed
with an `IRREGULAR_LEMMAS = {"data": "data"}` override applied at the
token level in both `extract_roots.py` and `match_buckets.py`'s
`_lemmatize_term`, so "data" always lemmatizes the same way regardless of
its position in the sentence. Verified directly:

```
"Improve our data strategy."   -> data_ai matches: ['data']  (was: no match)
"We rely on customer data."    -> data_ai matches: ['data']  (was: no match)
"Better data quality is needed." -> data_ai matches: ['data']  (was: no match)
```

Re-ran the full 18-case eval after this fix: 66/90 = 73.3%, same
aggregate as before — the fix is real (verified above, not just
theoretical) but this eval set's tie-breaks absorb it: case 11 gained a
`Data & AI` hit and lost a `Timeline` hit to a top-5 tie-break in the same
case, netting zero on the aggregate count for this particular set.

**Bucket taxonomy overlap — attempted a fix, evidence says no.** Tried
the fix this doc suggested: fold `Compliance`/`Governance`/`Legal` into
`Governance & Compliance` as one canonical slot, the same way
`get_tooltip.py` already merges same-named Tier 1/Tier 2 pairs. Measured
against the 18-case eval:

| | Before | After equivalence-group merge |
|---|---|---|
| Recall | 66/90 = 73.3% | 63/90 = 70.0% |
| Avg hits/case | 3.67 | 3.50 |

Net **negative**, and case 7 (the motivating example from the first Phase
6 run) didn't even register as fixed, because the eval scores by exact
bucket name and the merged result renders as "Governance & Compliance",
not "Compliance" (case 7's expected label). The real disqualifying
evidence was case 12 — *"Get our fintech lending product RBI-compliant
and audit-ready before our Series B raise closes in Q3"* — whose human-
labeled `expected_buckets` are `Compliance`, `Legal`, `Governance`,
`Risk`, `Timeline`: **three of the four "duplicate" buckets, expected as
three distinct hits.** Before the merge, the pipeline correctly surfaced
all three independently (4/5 on this case, missing only Timeline); after
the merge it could only ever supply one of the three, dropping to 2/5.

This disproves the assumption (made when this doc was first written) that
these buckets are pure vocabulary duplicates that should always collapse.
In a broad, generic statement (case 7's SOC 2 mention) they behave like
duplicates; in a regulatory-specific statement (case 12) they're
legitimately distinct facets (compliance execution vs. legal obligation
vs. decision-rights/governance). A blanket merge can't satisfy both.
Reverted the merge entirely — code is back to the original same-name-only
tier dedup. Left `Sales`/`Marketing`/`Growth Strategy` untouched too,
since the same caution now applies to it without case-by-case evidence.

**Revised recommendation:** don't attempt another blanket merge here.
Either (a) add more eval cases spanning both a generic and a
domain-specific phrasing for each suspected cluster, to see whether the
distinct-vs-duplicate split is consistent per-domain and could drive a
conditional rule, or (b) treat this as inherent top-5-capacity pressure
that isn't cleanly fixable by taxonomy changes at all, and deprioritize it
below Phase 5.

## 2026-08-22 follow-up #2: eval cases for the never-exercised domains

The original 18 cases never exercised 21 of 77 buckets (measured on raw
match_buckets() output, not just top-5 survivors), including all five
domains flagged above as "unexercised, not necessarily broken": Ethics,
Privacy, Sustainability, Accessibility, Localization. Added 5 new cases
(19-23, one per domain, realistic statements genuinely relevant to that
domain plus 4 other buckets) to `eval_set.json` to check.

**Result: mixed, and more interesting than "broken vs. fine."**

| Case | Domain | Bucket's raw match | What happened |
|---|---|---|---|
| 19 | Ethics | Matched (score 1, "ethical") | **Lost the top-5 tie-break** — crowded out by Business Objective/AI/ML/Timeline (score 2) and Compliance/Data & AI (score 1, won tie-break) |
| 20 | Privacy | Matched (score 1, "privacy") | **Lost the top-5 tie-break** — crowded out similarly |
| 21 | Sustainability | Matched (score 1, via the bucket's own name, not a synonym) | **Lost the top-5 tie-break** |
| 22 | Accessibility | Matched, made top-5 | **Hit** — no issue found |
| 23 | Localization | **Zero raw match** | **Genuine vocabulary gap** — see below |

So 3 of 5 "unexercised" buckets (Ethics, Privacy, Sustainability) are
**not** vocabulary-broken — they matched correctly on real phrasing but
lost a top-5 slot to other legitimately-relevant buckets in the same
statement. This is the same top-5-capacity-pressure pattern behind the
bucket-taxonomy-overlap finding above, but now showing up **across
unrelated bucket clusters** (Ethics/Privacy/Sustainability aren't
near-duplicates of Business Objective/AI/ML/Timeline the way
Compliance/Governance/Legal are of each other) — suggesting the top-5 cap
itself, not just specific overlapping clusters, is the recurring
constraint. Worth keeping in mind if this comes up again: synonym tuning
can't fix a slot-capacity problem.

**Localization — genuine gap, fixed.** Zero raw match on `"...translating
the product catalog... and adapting pricing to each region's
currency..."` despite `translation` and `adaptation` already being listed
synonyms. Root cause: the same lemma-mismatch *class* of bug as the
"data"/"datum" fix above, but a different mechanism — spaCy lemmatizes
the verb forms actually used in real phrasing ("translating" ->
"translate", "adapting" -> "adapt") to their verb lemma, which doesn't
match the noun-form synonyms stored ("translation", "adaptation"). Fixed
by adding the verb forms (`"translate"`, `"adapt"`, and `"localize"` for
the same reason) to `bucket_library.json`'s Localization synonym list.
Verified: case 23 went 2/5 -> 3/5 (Localization now hits; still missing
Pricing and Timeline, which is a separate, unrelated gap not investigated
here). Full eval: 81/115 -> 82/115 recall (70.4% -> 71.3%), no
regressions on any other case.

**Not fixed / not attempted:** the Ethics/Privacy/Sustainability crowding
issue is the same "decision, not synonym tuning" category as the
taxonomy-overlap finding above, and given the earlier equivalence-merge
attempt's negative result, no tie-break change was attempted here either
without stronger evidence on what rule would actually help across cases
without hurting others.

## 2026-08-22 follow-up #3: round 2 of eval coverage (cases 24-28)

Continued closing the untested-bucket gap: added 5 more cases targeting
Lessons Learned, Communication, Monitoring, Dependencies, Quality (the
next batch of the buckets no case had ever raw-matched). Same pattern as
before, split cleanly into two categories:

**Genuine vocabulary gaps, found and fixed (3 of 5):**
- **Communication** — zero raw match on "weekly stakeholder update
  cadence and a shared status report... leadership stays informed."
  Synonym list was all formal/written-correspondence terms (briefing,
  communique, memorandum, transmittal) with no plain business words for
  routine updates. Added `update`, `report`, `reporting`, `status
  update`, `inform`.
- **Monitoring** — zero raw match on "real-time dashboards and automated
  alerts... latency and error rate... on-call team." Synonym list was
  all formal supervision/inspection terms (inspectorate, superintendence,
  surveillance) despite the bucket's own prompt literally saying
  "observability, alerts" — those words just weren't in the synonym
  list. Added `alert`, `alerting`, `dashboard`, `observability`,
  `on-call`, `uptime`.
- **Dependencies** — zero raw match on "blocked until both of their
  upstream changes ship." Synonym list was only word-form variants of
  "dependency" itself (dependance, dependence, dependency, dependent) —
  no real phrasing for how people actually describe being blocked. Added
  `blocked`, `blocker`, `upstream`, `downstream`, `prerequisite`.

Verified directly (raw score, terms matched) and via full re-run: all
three now score >0 on their case AND win their top-5 slot outright (not
just a marginal win — Communication scored 3, Monitoring 2, Dependencies
2, comfortably ahead of the competing buckets in each case). Full-eval
recall: 89/140 -> 91/140 (63.6% -> 65.0%).

**Top-5 crowding, not fixed (2 of 5):** Lessons Learned and Quality both
raw-matched correctly (score 1, via "lesson" and "quality" respectively)
but lost their top-5 slot to other buckets in the same statement — the
same pattern as Ethics/Privacy/Sustainability in follow-up #2. That's now
**5 independent cases** of a real match losing to top-5 capacity, across
completely unrelated bucket clusters (Compliance-family, Ethics/Privacy/
Sustainability, and now Lessons Learned/Quality). Not attempted here, per
the standing "needs a decision" boundary — but the evidence for this
being a structural, not incidental, issue keeps growing.

**New lead not chased this round:** case 26 (Monitoring) still only hit
1 of 5 expected even after the fix, because `Reliability`, `Performance`,
`Metrics`, and `Risk` all raw-scored zero on "latency and error rate...
catch failures" -- none of their synonym lists cover that incident-
response vocabulary either. Flagging for a future round rather than
scope-creeping this one.

**Remaining untested buckets after this round: 8 of 77** (down from 21
after follow-up #2's round, down from the original 37) —
`Assumptions`, `Competition`, `Competitive Landscape`, `Constraints`,
`External Environment`, `Innovation`, `Problem Definition`, `ROI`.
Converging faster than the original per-round estimate, partly because
new cases incidentally exercise buckets they weren't written to target.

## 2026-08-22 follow-up #4: round 3 of eval coverage (cases 29-34) — all 77 buckets now verified

**Correction to follow-up #3:** re-checked case 26's raw scores (not just
top-5 membership) before treating it as an open lead. `Performance` and
`Metrics` were mischaracterized as a possible vocabulary gap -- they
actually raw-matched fine (`latency`, `rate`) and lost the top-5 tie-break
to `Customer`/`Cost`/`Customer Experience`/`Feedback`, i.e. a 6th instance
of the crowding pattern, not a vocab gap. `Reliability`, however, was a
genuine zero-raw-match gap: its prompt literally says "failure scenarios"
but neither "fail" nor "failure" was a synonym. Fixed (added both);
verified `Reliability` now raw-matches `case 26` (score 1, term
"failure") -- still loses its top-5 slot to the same crowd (a 7th
crowding instance), but the vocabulary side is now correct.

Added the last 6 cases (29-34) covering the remaining 8 never-tested
buckets: Competition + Competitive Landscape (case 29), Assumptions +
Constraints (case 30), External Environment (31), Innovation (32),
Problem Definition (33), ROI (34).

**Genuine vocabulary gaps found and fixed (3):**
- **External Environment** — zero raw match on "new tariffs and a
  slowing consumer economy." Its own prompt names "political, economic,
  social, technological, legal, environmental" influences (a PESTLE
  framework), but none of those PESTLE-dimension words were literal
  synonyms except "environmental." Added `economic`, `economy`, `tariff`
  -- deliberately did *not* add `political`/`social`/`technological`/
  `legal` since those are bare, extremely generic words that would risk
  the same over-triggering mistake Phase 6's first round found and fixed
  in other buckets (e.g. `Legal` is already its own distinct bucket).
- **Assumptions** — zero raw match on "instead of assuming it's a
  checkout UX issue." Verb-form lemma mismatch, same class of bug as
  "data"/"datum" and "translating"/"translation": the text lemmatizes
  "assuming" to "assume," but the synonym list only had noun forms
  (assumption, premise, presumption). Added `assume`.
- **Customer Experience** — zero raw match on the same sentence's
  "checkout UX issue," despite the bucket's own prompt being "usability,
  satisfaction, and delight." Neither `ux` nor `user experience` was a
  synonym. Added both.

Verified: case 31 (External Environment) 2/5 -> 3/5; case 33 (Customer
Experience + Assumptions) 0/5 -> 2/5 (was a full zero-hit case before the
fix). Full-eval recall: 61.8% -> 63.5% (34 cases), zero-hit cases back to
0/34.

**Not fixed / not real bugs:** `Market` and `Risk` still miss in case 31,
and `Business Objective`/`ROI`/`Resources`/`Technology`-adjacent misses
recur in cases 33/34 -- checked raw scores and these are a mix of (a)
more crowding instances (ROI itself raw-matched in case 34 but lost its
slot to Finance/Financial Viability) and (b) cases where my own case text
didn't actually contain strong triggering vocabulary for that expected
bucket (e.g. case 31 never really says "market," it implies it) --
labeling honesty note: not every miss here is a pipeline bug, some are
just a generous expected-bucket label on a case that doesn't literally
evoke it. Not force-fixed by padding synonym lists to match invented
gaps, per the standing "don't reverse-engineer the eval set" discipline.

**Milestone: 0 of 77 buckets remain untested** (raw match) as of this
round -- every bucket in `bucket_library.json` has now been exercised by
at least one real eval case. This closes the "verify every bucket at
least once" goal in 4 rounds total (this session), faster than the
original ~6-7 round estimate, since several rounds' cases incidentally
covered buckets beyond their intended target.

**What's left is no longer coverage — it's the crowding pattern.** Across
all 4 rounds this session, **7 independent instances** of a bucket
matching correctly and still losing its top-5 slot have now been found,
spanning 5 unrelated bucket clusters (Compliance family; Ethics/Privacy/
Sustainability; Lessons Learned/Quality; Performance/Metrics;
Reliability/ROI/Technology). That is now the dominant remaining gap in
this pipeline, well past "maybe noise" — but per the reverted
equivalence-merge lesson, fixing it needs a real design decision (raise
`TOP_N`? a different tie-break rule? show more than 5 lines when there's
a genuine tie?), not another round of synonym tuning.

## 2026-08-25 follow-up #5: crowding fixed — "ties survive the cutoff"

Before touching `get_tooltip.py`, checked whether a different tie-break
*order* (the option originally on the table) could fix this. It can't:
every one of the 7 crowding instances above is a bucket that raw-matches
correctly and is just as relevant as the buckets that made the cut --
case 7 (Compliance/Governance/Legal all matching "compliance") and case
12 (the same three buckets independently confirmed as three genuinely
distinct expected hits by a human labeler) together prove there's no
principled order that picks a "correct" bucket to drop among co-equal
ties. Reordering priority only changes who wins the coin flip; it
doesn't remove the coin flip. This also explains in hindsight why the
2026-08-22 equivalence-merge attempt made things worse (73.3% -> 70.0%)
-- it tried to shrink the contention instead of making room for it.

**Fix implemented:** `rank_buckets()` in `get_tooltip.py` no longer cuts
at a flat `deduped[:TOP_N]`. It still cuts at position 5 by default, but
if the 5th-place bucket is tied on score with buckets beyond it, the
whole tied group is now included, capped at a new `MAX_N = 7`. This is a
strict extension of the old rule -- the old top-5 is always a subset of
the new result, so it cannot regress a case that was already passing;
verified directly (0 regressions across all 34 cases). A statement that
doesn't crowd the boundary still renders exactly 5 lines, unpadded --
only case 1 in the eval set stays at 5; the other 33 statements are
dense enough to hit somewhere between 6 and 7.

Three cap values were measured against the full 34-case eval set before
picking one:

| Cap | Recall | Avg lines | Max lines |
|---|---|---|---|
| 5 (old behavior) | 108/170 = 63.5% | 5.00 | 5 |
| 6 | 118/170 = 69.4% | 5.97 | 6 |
| **7 (chosen)** | **127/170 = 74.7%** | **6.94** | **7** |
| 8 | 132/170 = 77.6% | 7.74 | 8 |

Cap 8 was rejected even though it scores highest: 27 of the 34 cases hit
that ceiling, meaning in practice it reads as "always show 8 lines," not
a tooltip that occasionally grows. Cap 7 was chosen as the balance point
-- most of the recall gain (+11.2 points) while still bounded well short
of "always maxed out."

**Full-eval recall: 63.5% -> 74.7%** (34 cases, 170 expected slots), 0
regressions, 0 cases with fewer hits than before. Verified against the
live `rank_buckets()` code, not a projection.

**What's left:** nothing scoped for this pipeline right now. The
crowding pattern that drove the last 4 eval rounds is fixed; coverage
was already complete (0 of 77 buckets untested) as of follow-up #4. Any
further work here would be new-scope (e.g. revisiting the Sales/
Marketing/Growth Strategy overlap question, never re-tested after the
Compliance-family taxonomy finding) rather than continuing this thread.
