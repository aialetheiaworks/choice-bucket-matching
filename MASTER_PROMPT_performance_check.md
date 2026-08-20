# Master Prompt — Check Current Bucket Matching Performance

Paste this into Claude Code, in the same folder/repo where the matching
pipeline lives (with `bucket_library.json` and `eval_set.json` present).

---

```
Read eval_set.json in this folder. It contains 18 realistic objective
statements, each with a human-labeled "expected_buckets" list — the
buckets that should reasonably show up in that statement's top-5 tooltip.

Run each case's "objective" text through the current bucket matching
pipeline exactly as a real user query would go through it (treat the
objective text as both the raw query and the master prompt input, since
there's no live Choice Forge output to test against here).

For each of the 18 cases, capture:
- the top-5 predicted buckets, in rank order, with their scores
- which root words/terms triggered each predicted bucket
- how many of the expected_buckets appear anywhere in the predicted top-5
  (a "hit"), and which expected buckets were missed entirely

Then produce a performance report with:

1. A per-case table: case id, hit count out of 5 expected, which expected
   buckets were missed, and any predicted buckets that seem clearly wrong
   or irrelevant to the objective (false positives).
2. Aggregate numbers across all 18 cases: average hits per case, total
   misses, total buckets that never appeared in ANY case's top-5 across
   the whole eval set (dead buckets — likely means their synonym list is
   too thin or their scoring weight is too low), and any bucket that
   appeared in an unusually high number of cases regardless of relevance
   (over-triggering — likely means its synonym list is too broad/generic).
3. A short list of the worst-performing cases (lowest hit count) with your
   best guess at WHY — e.g. "case 9 missed Pricing & Monetization because
   'freemium' isn't in that bucket's synonym list."

Do not change bucket_library.json, the synonym lists, or any scoring
weights yet. This is a read-only performance check — report findings only,
and stop. I'll decide what to fix based on the report.
```

---

## Why this is the right first performance check

This tests the pipeline end-to-end (extraction → matching → ranking →
top-5 selection) against realistic, varied objective statements — not just
the one office-chairs example from the original doc — so it surfaces real
gaps in the synonym lists and scoring logic before you ship. It's
deliberately read-only: the goal here is a diagnosis, not an autofix, so
you get to see exactly what's broken before anything changes underneath
you.

## After you get the report back

Expect some real misses — the synonym lists were built from WordNet +
Datamuse + manual seeding and reviewed once, not battle-tested against
real phrasing yet. Common likely gaps based on how the lists were built:
casual/modern business terms (freemium, churn, NPS, bundling, attrition)
may not be well covered since WordNet skews formal/dictionary-style and
Datamuse's tighter `rel_syn` mode also skews formal. If a term shows up
as a miss, the fix is almost always "add that literal term to the
relevant bucket's synonym list in bucket_library.json" — cheap, targeted,
and exactly the kind of real-evidence-driven tuning this design was built
around, rather than guessing at coverage gaps upfront.
