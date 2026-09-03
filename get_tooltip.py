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
- Content dedup (DEDUP_SIMILAR_PROMPTS, 2026-09-03): after the sort, drop
  any bucket whose prompt near-duplicates a higher-ranked bucket's (e.g.
  Market vs Market Opportunity -- ~12 Tier-1/Tier-2 twin pairs exist).
  Runs before the cut below so a freed slot goes to a real bucket. The
  library is untouched -- see _dedupe_similar_prompts and follow-up #8.
- Zero matches: fall back to exactly CORE_BUCKETS (all 5), in priority
  order.
- 1-4 matches: show that many lines, not padded with core buckets -- a
  short accurate tooltip beats a padded generic one.
- 5+ matches: top 5 by the ranking above, EXCEPT when the bucket in 5th
  place is tied on score with buckets beyond it -- then the whole tied
  group is shown, capped at MAX_N. "Ties survive the cutoff": a hard
  cut at position 5 previously discarded a tied bucket for no reason but
  alphabetical luck, even when it was just as relevant as the one that
  made the cut. See PHASE6_EVAL_RESULTS.md's crowding-pattern writeup
  (2026-08-22 -> 2026-08-25) for the evidence this fixes: 7 independent
  instances across 5 unrelated bucket clusters where a correctly-matched
  bucket lost only to slot-count, not relevance. A short statement that
  doesn't crowd the boundary still shows exactly 5 lines -- this only
  grows the tooltip when the tie genuinely goes deeper than 5.

  **MAX_N raised 7 -> 9 (2026-09-01):** the chunk-priority phrase-matching
  fix (extract_roots.py/match_buckets.py -- vocabulary-driven longest-match
  scanning with sub-word suppression, per stakeholder feedback) reduces
  redundant "noise" scores that used to let some buckets win clean top
  slots outright. That pushed more buckets into score ties, so the old
  MAX_N=7 cap started cutting genuine matches, not just noise -- recall on
  the 34-case eval dropped 75.9% -> 71.8% at MAX_N=7 with the new matching
  logic. Measured the cap directly: 9 -> 78.2%, 12 -> 81.8% (ceiling, same
  as uncapped -- no case's tied group exceeds 12). Raised to 9 as the
  chosen tradeoff (user's call, not guessed): clears the pre-fix baseline
  while keeping the tooltip list closer to its original length than 12
  would (most statements now show close to 9 lines, up from 5-7).

  **Salience scoring interaction (2026-09-02):** when match_buckets.py runs
  in SCORING_MODE="salience", scores are continuous (summed dependency-
  salience weights) rather than integer term counts, so exact ties at the
  position-5 boundary are rare and the tied-group extension above almost
  always returns exactly TOP_N. That is the intended effect -- the crowding
  pattern this MAX_N machinery exists to contain is largely a symptom of
  integer scores producing large tied groups. The machinery is kept as-is:
  it is a no-op on well-separated scores and still bounds the occasional
  genuine tie. MAX_N still applies as the hard ceiling.

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

import re
import sys

from match_buckets import load_bucket_index, match_buckets, SCORING_MODE
from match_logger import log_match

CORE_BUCKETS = ["Business Objective", "Customer", "Value Proposition", "Risk", "Market"]
TOP_N = 5
MAX_N = 9

# How the ranked list is ordered (2026-09-02). match_buckets.py attaches
# both a count_score (distinct matched terms) and a salience_score (those
# terms' summed dependency-salience weights) to every result, so ranking
# can use either or both:
#   "count"            -- sort by count_score; ties broken by core priority
#                         then name (the original behaviour, unchanged).
#   "salience"         -- sort by salience_score directly. Continuous, so
#                         the boundary ties MAX_N exists to bound mostly
#                         vanish -- but eval shows this trades ~15pt of
#                         full-list recall for shorter, higher-precision
#                         lists (see PHASE6_EVAL_RESULTS.md 2026-09-02).
#   "count_salience"   -- sort by count_score, then break ties by
#                         salience_score (more syntactically central bucket
#                         wins the slot), then core priority, then name.
#                         Keeps count's recall; only changes who wins ties.
# Must line up with match_buckets.SCORING_MODE for "salience" (that mode
# is what makes score == salience_score); "count" and "count_salience"
# both work with SCORING_MODE="count".
RANK_MODE = "count_salience"

# Content dedup (2026-09-03). Several Tier-2 "strategic lens" buckets have
# prompt text that substantially restates a Tier-1 bucket's -- e.g. Market
# ("market size, maturity, growth, and dynamics") vs Market Opportunity
# ("market size, growth potential, attractiveness, maturity, whitespace").
# When both rank, the tooltip shows the same guidance twice. This drops a
# bucket whose prompt overlaps a higher-ranked bucket's prompt by at least
# PROMPT_OVERLAP_THRESHOLD (shared content words / smaller prompt's content
# word count). The higher-ranked twin is always the one kept -- and since a
# Tier-1 bucket sorts ahead of its Tier-2 twin on the existing tie-break,
# the Tier-1 prompt wins by default, consistent with _dedupe_tiers.
#
# This is the display-time half of the bucket-overlap question (12 T1/T2
# twin pairs, see PHASE6_EVAL_RESULTS.md follow-up #8). It does NOT touch
# bucket_library.json -- whether the twins should be merged or their
# prompts rewritten is a taxonomy decision for the stakeholders.
DEDUP_SIMILAR_PROMPTS = True
PROMPT_OVERLAP_THRESHOLD = 0.75

# Boilerplate that every "consider X, Y, Z" prompt shares -- ignored when
# comparing prompts so the overlap score reflects actual guidance content.
_PROMPT_STOPWORDS = {
    "consider", "assess", "evaluate", "identify", "the", "a", "an", "and",
    "or", "of", "to", "for", "in", "with", "whether", "should", "come",
    "together", "be", "is", "are", "this", "that", "its", "their", "our",
    "how", "will", "as",
}


def _prompt_content_words(text):
    """Meaningful words in a bucket prompt: lowercased, boilerplate and
    short tokens dropped, trailing -s stripped so plural/singular match
    (crude but enough for these short curated strings)."""
    words = set()
    for raw in re.findall(r"[a-zA-Z]+", text.lower()):
        if len(raw) <= 2 or raw in _PROMPT_STOPWORDS:
            continue
        words.add(raw[:-1] if raw.endswith("s") else raw)
    return words


def _near_duplicate_prompt(words_a, words_b):
    """True if two prompt content-word sets overlap by at least
    PROMPT_OVERLAP_THRESHOLD, measured as shared / smaller set (overlap
    coefficient -- so a short prompt fully contained in a longer one
    counts as a duplicate even though Jaccard would look low)."""
    if not words_a or not words_b:
        return False
    shared = len(words_a & words_b)
    return shared / min(len(words_a), len(words_b)) >= PROMPT_OVERLAP_THRESHOLD


def _dedupe_similar_prompts(ranked):
    """Drop any bucket whose prompt near-duplicates a higher-ranked
    bucket's (see DEDUP_SIMILAR_PROMPTS). Input must already be sorted --
    the earlier bucket in the list is the one kept."""
    kept = []
    kept_words = []
    for r in ranked:
        words = _prompt_content_words(r["prompt"])
        if any(_near_duplicate_prompt(words, w) for w in kept_words):
            continue
        kept.append(r)
        kept_words.append(words)
    return kept


def _core_rank(name):
    """Index of `name` in CORE_BUCKETS, or len(CORE_BUCKETS) if not core
    -- sort key so core buckets win score ties in their declared priority
    order, and non-core ties fall through to the alphabetical tiebreak."""
    return CORE_BUCKETS.index(name) if name in CORE_BUCKETS else len(CORE_BUCKETS)


def _rank_sort_key(r, rank_mode):
    """Ranking sort key per rank_mode (see RANK_MODE's comment). Lower
    sorts first, so scores are negated."""
    if rank_mode == "salience":
        return (-r["salience_score"], _core_rank(r["name"]), r["name"])
    if rank_mode == "count_salience":
        return (-r["count_score"], -r["salience_score"], _core_rank(r["name"]), r["name"])
    return (-r["count_score"], _core_rank(r["name"]), r["name"])


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
        # Union the per-term salience weights (a term matched in both tiers
        # keeps its larger weight), then re-derive every score from that so
        # count_score / salience_score / score all stay consistent for the
        # merged entry regardless of which one Phase 3 ranks on.
        merged_weights = dict(existing.get("term_weights", {}))
        for term, weight in r.get("term_weights", {}).items():
            merged_weights[term] = max(weight, merged_weights.get(term, 0.0))
        existing["term_weights"] = merged_weights
        existing["matched_terms"] = sorted(merged_weights)
        existing["count_score"] = len(merged_weights)
        existing["salience_score"] = round(sum(merged_weights.values()), 4)
        existing["score"] = (
            existing["salience_score"] if SCORING_MODE == "salience"
            else existing["count_score"]
        )
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
            "count_score": 0,
            "salience_score": 0.0,
            "matched_terms": [],
            "term_weights": {},
        }
        for name in CORE_BUCKETS
        if name in by_name
    ]


def rank_buckets(match_results, bucket_index, master_prompt=None, log=True,
                 rank_mode=None, dedup=None):
    """Phase 3: turn match_buckets()'s per-bucket scores into the final
    ranked selection (see module docstring for the rules).

    Also Phase 5 (persistence): this is the one point every front end (CLI,
    Flask, Gradio, Streamlit) already calls with both match_results and the
    final ranked list, so it's the chokepoint for logging a run -- see
    match_logger.py. `master_prompt` is optional so existing callers don't
    break; pass it to get the query text captured in the log. `log=False`
    skips the log write -- used by the Phase 6 eval harness so batch runs
    don't accumulate in match_log.jsonl. `rank_mode` overrides the module
    RANK_MODE constant, `dedup` overrides DEDUP_SIMILAR_PROMPTS (both for
    the eval harness's A/B runs)."""
    if rank_mode is None:
        rank_mode = RANK_MODE
    if dedup is None:
        dedup = DEDUP_SIMILAR_PROMPTS
    if not match_results:
        ranked = _core_bucket_fallback(bucket_index)
    else:
        deduped = _dedupe_tiers(match_results)
        deduped.sort(key=lambda r: _rank_sort_key(r, rank_mode))
        # Drop near-duplicate-content buckets BEFORE the TOP_N/MAX_N cut, so
        # removing a redundant line frees a real slot for the next genuine
        # bucket rather than just shortening the list.
        if dedup:
            deduped = _dedupe_similar_prompts(deduped)
        if len(deduped) <= TOP_N:
            ranked = deduped
        else:
            # The boundary tie is on the PRIMARY score (integer count in
            # "count"/"count_salience", salience in "salience"); MAX_N still
            # bounds a runaway tie group. In "count_salience" the group is
            # already ordered by salience_score, so the salience tiebreak
            # decides which of a tied count-tier's members make the cut.
            cutoff_score = deduped[TOP_N - 1]["score"]
            tied = [r for r in deduped if r["score"] >= cutoff_score]
            ranked = tied[:MAX_N]

    if log:
        log_match(master_prompt, match_results, ranked)
    return ranked


def render_tooltip(ranked):
    """Phase 4: render each ranked bucket's tooltip line. Stakeholder
    feedback (2026-09-01) dropped the "If you are speaking about X, also
    consider thinking about" framing -- the prompt text alone is the
    tooltip line now."""
    return [r["prompt"] for r in ranked]


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
