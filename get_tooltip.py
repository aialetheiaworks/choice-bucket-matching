#!/usr/bin/env python3
"""
get_tooltip.py

Phases 3-4 of the CHOICE bucket-matching pipeline (see
CLAUDE_CODE_BUILD_BRIEF.md): takes Phase 2's per-bucket match scores,
ranks them into a final top-5 (or fewer) selection, and renders the
tooltip lines shown to the user.

Phase 3 -- ranking:
- Tier dedup: when a bucket name matched in both Tier 1 and Tier 2 (e.g.
  "Value Proposition", "Product Strategy", "Continuous Improvement"),
  merge into a single line -- matched terms from both tiers combine for
  scoring/recall, but the rendered prompt text always comes from the
  Tier 1 (shorter) entry.
- Sort by score descending. Tie-break: a bucket in CORE_BUCKETS outranks
  one that isn't, in CORE_BUCKETS's priority order; non-core ties break
  alphabetically by name for determinism.
- Zero matches: fall back to exactly CORE_BUCKETS (all 5), in priority
  order.
- 1-4 matches: show that many lines, not padded with core buckets -- a
  short accurate tooltip beats a padded generic one.
- 5+ matches: top 5 by the ranking above, EXCEPT when the bucket in 5th
  place is tied on score with buckets beyond it -- then the whole tied
  group is shown, capped at MAX_N (7). "Ties survive the cutoff": a hard
  cut at position 5 previously discarded a tied bucket for no reason but
  alphabetical luck, even when it was just as relevant as the one that
  made the cut. See PHASE6_EVAL_RESULTS.md's crowding-pattern writeup
  (2026-08-22 -> 2026-08-25) for the evidence this fixes: 7 independent
  instances across 5 unrelated bucket clusters where a correctly-matched
  bucket lost only to slot-count, not relevance. Measured against the
  34-case eval set: 63.5% -> 74.7% recall, zero regressions (this rule is
  a strict extension of the old top-5, never a replacement of it). A
  short statement that doesn't crowd the boundary still shows exactly 5
  lines -- this only grows the tooltip when the tie genuinely goes deeper
  than 5.

Phase 4 -- rendering: plug each ranked bucket into the tooltip template,
capped at 5 lines.

This module takes manual master-prompt input for now (CLI arg or
interactive prompt) -- Choice Forge integration is a later step, not
part of this build.

Usage:
    python3 get_tooltip.py "<master prompt>"
    python3 get_tooltip.py                      # prompts interactively
    # or: from get_tooltip import get_tooltip
"""

import sys

from match_buckets import load_bucket_index, match_buckets
from match_logger import log_match

CORE_BUCKETS = ["Business Objective", "Customer", "Value Proposition", "Risk", "Market"]
TOP_N = 5
MAX_N = 7

TEMPLATE = "If you are speaking about {name}, also consider thinking about → {prompt}."


def _core_rank(name):
    """Index of `name` in CORE_BUCKETS, or len(CORE_BUCKETS) if not core
    -- sort key so core buckets win score ties in their declared priority
    order, and non-core ties fall through to the alphabetical tiebreak."""
    return CORE_BUCKETS.index(name) if name in CORE_BUCKETS else len(CORE_BUCKETS)


def _dedupe_tiers(results):
    """Merge same-named buckets that matched in both Tier 1 and Tier 2
    into one entry: matched terms union for scoring/recall, but the
    rendered prompt always comes from the Tier 1 (shorter) text -- per
    the 2026-08-18 decision in the build brief.

    An equivalence-group merge (folding Compliance/Governance/Legal/
    Governance & Compliance into one canonical slot) was tried here and
    measured against eval_set.json: it dropped recall 73.3% -> 70.0% and
    didn't even fix its target case (case 7) under the eval's exact-name
    scoring, because case 12 shows these are NOT reliably duplicates --
    a regulatory-compliance statement where a human labeler expects
    Compliance, Legal, and Governance as three genuinely distinct hits.
    Reverted; see PHASE6_EVAL_RESULTS.md for the full writeup. The
    bucket-taxonomy-overlap question is still open."""
    by_name = {}
    for r in results:
        existing = by_name.get(r["name"])
        if existing is None:
            by_name[r["name"]] = dict(r)
            continue
        merged_terms = sorted(set(existing["matched_terms"]) | set(r["matched_terms"]))
        existing["matched_terms"] = merged_terms
        existing["score"] = len(merged_terms)
        if r["tier"] == 1 and existing["tier"] != 1:
            existing["prompt"] = r["prompt"]
            existing["tier"] = 1
    return list(by_name.values())


def _core_bucket_fallback(bucket_index):
    """Zero-match fallback: exactly CORE_BUCKETS, in priority order,
    using each bucket's Tier 1 definition."""
    by_name = {b["name"]: b for b in bucket_index if b["tier"] == 1}
    return [
        {
            "id": by_name[name]["id"],
            "name": name,
            "tier": 1,
            "prompt": by_name[name]["prompt"],
            "score": 0,
            "matched_terms": [],
        }
        for name in CORE_BUCKETS
        if name in by_name
    ]


def rank_buckets(match_results, bucket_index, master_prompt=None):
    """Phase 3: turn match_buckets()'s per-bucket scores into the final
    ranked selection (see module docstring for the rules).

    Also Phase 5 (persistence): this is the one point every front end (CLI,
    Flask, Gradio, Streamlit) already calls with both match_results and the
    final ranked list, so it's the chokepoint for logging a run -- see
    match_logger.py. `master_prompt` is optional so existing callers don't
    break; pass it to get the query text captured in the log."""
    if not match_results:
        ranked = _core_bucket_fallback(bucket_index)
    else:
        deduped = _dedupe_tiers(match_results)
        deduped.sort(key=lambda r: (-r["score"], _core_rank(r["name"]), r["name"]))
        if len(deduped) <= TOP_N:
            ranked = deduped
        else:
            cutoff_score = deduped[TOP_N - 1]["score"]
            tied = [r for r in deduped if r["score"] >= cutoff_score]
            ranked = tied[:MAX_N]

    log_match(master_prompt, match_results, ranked)
    return ranked


def render_tooltip(ranked):
    """Phase 4: render each ranked bucket into the tooltip template.
    Bucket prompts in bucket_library.json already end in a period, so
    strip a trailing one before formatting to avoid a double period."""
    return [
        TEMPLATE.format(name=r["name"].upper(), prompt=r["prompt"].rstrip("."))
        for r in ranked
    ]


def get_tooltip(master_prompt):
    """Run the full pipeline (Phases 1-4) end to end: master prompt in,
    final rendered tooltip lines out."""
    bucket_index = load_bucket_index()
    match_results = match_buckets(master_prompt, bucket_index=bucket_index)
    ranked = rank_buckets(match_results, bucket_index, master_prompt=master_prompt)
    return render_tooltip(ranked)


def main():
    if len(sys.argv) > 2:
        print('Usage: python3 get_tooltip.py "<master prompt>"')
        sys.exit(1)
    master_prompt = sys.argv[1] if len(sys.argv) == 2 else input("Master prompt: ")
    lines = get_tooltip(master_prompt)
    print()
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
