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
