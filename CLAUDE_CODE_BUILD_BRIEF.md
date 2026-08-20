# CHOICE Bucket Matching Engine — Build Brief for Claude Code

This is the sequenced build plan for the root-word bucket matching pipeline
(the "Intent Classifier / Pattern Matching" step in the Decision Intelligence
Platform architecture). Two inputs are already done and included in this
folder — start from these, don't regenerate them:

- `bucket_library.json` — structured Tier 1 (60 buckets) + Tier 2 (20 buckets)
  from the Knowledge Bucket Library doc, with an empty `synonyms: []` field
  per bucket, ready to be filled in.
- `generate_synonyms.py` / `merge_reviewed_synonyms.py` — scripts to build
  and merge synonym candidates from WordNet + Datamuse (+ optional
  Merriam-Webster) into `bucket_library.json`.

**Decision already made (don't relitigate in Claude Code):** ship v1 with
synonym-list-only matching. No spaCy vector/cosine-similarity fallback in
v1 — it's expensive to tune and not worth it until real usage data shows a
genuine coverage gap. Log zero/low-match queries in production and revisit
semantic fallback later if the data justifies it.

**Decision confirmed 2026-08-19 — single master-prompt input:** the pipeline
takes only the Choice Forge master prompt as input now. The separate raw
user query is dropped from this flow entirely — Choice Forge already
consumes the raw query to produce the master prompt, so this pipeline
doesn't need it a second time. This removes the query-vs-master-prompt
source weighting from Phase 2 (there's only one source now) and simplifies
Phase 1 to a single-document extraction. `extract_roots.py` and
`match_buckets.py` have already been updated to this signature.

---

## Phase 0 — Synonym list generation (do this first, before any pipeline code)

1. `pip install nltk requests`
2. `python3 -m nltk.downloader wordnet omw-1.4` (needs normal network access —
   this failed in the sandboxed research environment but will work on a
   normal dev machine/CI runner)
3. (Optional) get a free Merriam-Webster Thesaurus API key and
   `export MERRIAM_WEBSTER_API_KEY=...` before running the script, for a
   third, editorially-curated source.
4. `python3 generate_synonyms.py` → produces `bucket_synonyms_review.csv`
5. **Human review pass (you, not Claude Code):** open the CSV, mark
   `approve (y/n)` per candidate term. Datamuse's `ml=` (loosely-related)
   results in particular need pruning — expect to reject a meaningful
   fraction of candidates, especially for abstract buckets (Innovation,
   Quality, Ethics) where "related" words drift off-topic fast.
6. `python3 merge_reviewed_synonyms.py` → writes approved synonyms back into
   `bucket_library.json`.
7. Spot-check a handful of buckets by hand afterward — especially
   business-domain terms your users will actually type (SME, GTM, D2C,
   lakh/crore, churn, MRR, etc.) that generic thesaurus sources won't know
   about. Add these manually to the relevant bucket's `synonyms` array.

**Output of this phase:** `bucket_library.json` fully populated with
curated synonym lists for all 80 buckets. This is the dictionary the
matching engine looks up against — get this right before writing any
matching code, since bad input here can't be fixed by good matching logic.

---

## Phase 1 — NLP extraction pipeline (spaCy, lemmatization only — no vectors)

- Install `en_core_web_sm` (small model is fine here — no vector similarity
  needed in v1, so the larger vector-carrying models aren't required).
- Input: the Choice Forge master prompt only (2026-08-19: the separate raw
  user query is no longer a pipeline input — see the decision above).
- Pipeline: tokenize → remove stopwords → keep NOUN/PROPN/VERB/ADJ →
  lemmatize → also extract noun chunks (`doc.noun_chunks`) for multi-word
  bucket names like "Value Proposition" or "Business Objective".
- Output: a deduplicated set of root words + root phrases for that master
  prompt.
- **Decision confirmed 2026-08-18:** a negated phrase like "without
  expanding the sales team" still counts as a match for Resources/Talent.
  Negation is not suppressed and does not need to be detected in Phase 1 —
  lemmatize and match as normal.

---

## Phase 2 — Matching engine

- For each bucket, check whether any extracted root word/phrase matches the
  bucket's `name` or any entry in its `synonyms` list (lemma-to-lemma
  comparison, not substring matching — lemmatize the synonym list once at
  load time too).
- Score each bucket: `score = (# distinct matched terms)`. (2026-08-19: the
  earlier master-prompt-vs-raw-query weighting no longer applies — there's
  only one input source now, so every matched term counts equally.)
- **Decision confirmed 2026-08-18:** match against both tiers (all 80
  buckets) for scoring/recall. When a bucket name overlaps both tiers
  (Value Proposition, Product Strategy, Continuous Improvement), dedupe
  to a single tooltip line using the Tier 1 (shorter) prompt, even though
  the Tier 2 entry also matched.

---

## Phase 3 — Ranking & top-5 selection

- Sort matched buckets by score, descending.
- Take top 5.
- **Decision confirmed 2026-08-18 — tie-break + zero-match core list
  (one shared config value, not two):** the "core" bucket list is
  `["Business Objective", "Customer", "Value Proposition", "Risk",
  "Market"]`, in that priority order. Used two ways: (1) on a score tie,
  a bucket in this list outranks one not in it, in the list's order; (2)
  on zero matches, this is exactly what gets shown as the fallback
  (subject to the fewer-than-5 rule immediately below, so zero-match
  actually renders all 5 of these lines, not just the first 2). Keep this
  as a single named config value (e.g. `CORE_BUCKETS`) so both call sites
  read from the same source instead of drifting apart.
- **Decision confirmed 2026-08-18 — fewer-than-5 case:** if only 2-3
  buckets clear the match threshold, show fewer lines rather than padding
  with irrelevant core-bucket suggestions. A short, accurate tooltip beats
  a padded, generic one.

---

## Phase 4 — Tooltip rendering

- Template: `"If you are speaking about {BUCKET NAME}, also consider
  thinking about → {prompt}."`
- Cap at 5 lines, ordered by rank from Phase 3.

---

## Phase 5 — Persistence & logging

Per the original Knowledge Graph requirements, every run should save:
1. The user's typed responses (raw query + master prompt)
2. The matched buckets, their scores, and which terms triggered each match
   (needed for debugging + future tuning, and for the "why was this
   suggested" transparency if you ever want to show it to the user)
3. **Specifically log zero-match and low-match (1 bucket only) queries** —
   this is the dataset that will tell you, with real evidence, whether the
   spaCy semantic-similarity fallback is ever actually worth building.
   Without this logging, Phase 6 below can't be an evidence-based decision.

---

## Phase 6 — Evaluation before shipping

- Build a small labeled test set: 15-20 realistic objective statements
  (in the style of the office chairs example) with a human-decided "these
  buckets should match" answer key.
- Run the pipeline against it, check precision (are the suggested buckets
  actually relevant?) and recall (did it miss anything obvious?).
- Tune synonym lists and the scoring weights (not thresholds — there's no
  cosine threshold to tune in this v1 design) based on what the eval set
  reveals.

---

## Explicitly out of scope for this build (separate, later work)

- The Knowledge Graph itself (nodes/edges, actor/relationship modeling,
  partial views) — that's a separate system that *consumes* this matching
  engine's output, not part of it.
- The spaCy semantic-vector fallback — only revisit if Phase 5's logging
  shows a real, recurring coverage gap in production.
- Tier 2 framework tools (dedicated PESTLE/SWOT/etc. products) — out of
  scope for the bucket matching engine itself.
