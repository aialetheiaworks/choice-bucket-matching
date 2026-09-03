#!/usr/bin/env python3
"""
eval_harness.py

Phase 6 evaluation harness (see CLAUDE_CODE_BUILD_BRIEF.md). Runs every case
in eval_set.json through the full pipeline and reports precision/recall
against the human-labeled expected_buckets, per the eval set's own
"how_to_score" rule.

Before 2026-09-02 this was always an uncommitted scratch script re-written
each session (see PHASE6_EVAL_RESULTS.md). Committed now so the number is
reproducible and A/B comparisons (scoring mode, ranking mode, MAX_N,
vocabulary changes) are one command.

Configs (scoring mode / ranking mode / prompt dedup -- see
match_buckets.SCORING_MODE, get_tooltip.RANK_MODE, DEDUP_SIMILAR_PROMPTS):
    count                 count / count / off
    count_salience        count / count_salience / off
    count_salience_dedup  count / count_salience / on   (current live default)
    salience              salience / salience / off

Usage:
    python3 eval_harness.py                       # current configured default
    python3 eval_harness.py --config count_salience
    python3 eval_harness.py --compare             # all three, side by side
    python3 eval_harness.py --compare --verbose   # + per-case hit/miss diff
"""

import argparse
import json
from pathlib import Path

from match_buckets import load_bucket_index, match_buckets, SCORING_MODE
from get_tooltip import rank_buckets, RANK_MODE, TOP_N, DEDUP_SIMILAR_PROMPTS

EVAL_FILE = Path(__file__).parent / "eval_set.json"

# name -> (scoring mode, rank mode, prompt dedup)
CONFIGS = {
    "count": ("count", "count", False),
    "count_salience": ("count", "count_salience", False),
    "count_salience_dedup": ("count", "count_salience", True),
    "salience": ("salience", "salience", False),
}


def _norm(name):
    """Eval scoring compares on base bucket name, ignoring any _v2/tier
    suffix. Library names carry no such suffix today, so this is just a
    defensive lowercase/strip."""
    return name.lower().strip().removesuffix("_v2").strip()


def run_case(case, bucket_index, scoring, rank_mode, dedup):
    results = match_buckets(case["objective"], bucket_index=bucket_index, scoring=scoring)
    ranked = rank_buckets(results, bucket_index, log=False, rank_mode=rank_mode, dedup=dedup)
    predicted_full = [r["name"] for r in ranked]
    predicted_top5 = predicted_full[:TOP_N]

    expected = {_norm(b) for b in case["expected_buckets"]}
    hits_top5 = [p for p in predicted_top5 if _norm(p) in expected]
    hits_full = [p for p in predicted_full if _norm(p) in expected]
    predicted_norm = {_norm(p) for p in predicted_full}
    missed = [b for b in case["expected_buckets"] if _norm(b) not in predicted_norm]
    return {
        "id": case["id"],
        "predicted_full": predicted_full,
        "n_hits_top5": len(hits_top5),
        "n_hits_full": len(hits_full),
        "n_expected": len(case["expected_buckets"]),
        "n_lines": len(predicted_full),
        "hits_full": sorted(hits_full),
        "missed": sorted(missed),
    }


def evaluate(config_name, bucket_index, cases):
    scoring, rank_mode, dedup = CONFIGS[config_name]
    rows = [run_case(c, bucket_index, scoring, rank_mode, dedup) for c in cases]
    tot_exp = sum(r["n_expected"] for r in rows)
    tot_hit_top5 = sum(r["n_hits_top5"] for r in rows)
    tot_hit_full = sum(r["n_hits_full"] for r in rows)
    return {
        "config": config_name,
        "rows": rows,
        "recall_top5": tot_hit_top5 / tot_exp,
        "recall_full": tot_hit_full / tot_exp,
        "precision_full": sum(r["n_hits_full"] / max(r["n_lines"], 1) for r in rows) / len(rows),
        "avg_lines": sum(r["n_lines"] for r in rows) / len(rows),
        "zero_hit_cases": [r["id"] for r in rows if r["n_hits_full"] == 0],
        "tot_hit_top5": tot_hit_top5,
        "tot_hit_full": tot_hit_full,
        "tot_exp": tot_exp,
    }


def print_summary(res):
    print(f"  config            : {res['config']}")
    print(f"  recall (full list): {res['recall_full']:.1%}  ({res['tot_hit_full']}/{res['tot_exp']})")
    print(f"  recall (top {TOP_N})    : {res['recall_top5']:.1%}  ({res['tot_hit_top5']}/{res['tot_exp']})")
    print(f"  precision (full)  : {res['precision_full']:.1%}")
    print(f"  avg lines shown   : {res['avg_lines']:.2f}")
    print(f"  zero-hit cases    : {res['zero_hit_cases'] or 'none'}")


def print_diff(res_a, res_b):
    by_id_a = {r["id"]: r for r in res_a["rows"]}
    print(f"\nPer-case full-list hits: {res_a['config']} -> {res_b['config']}")
    for rb in res_b["rows"]:
        ra = by_id_a[rb["id"]]
        da, db = ra["n_hits_full"], rb["n_hits_full"]
        if da == db:
            continue
        flag = "IMPROVED" if db > da else "REGRESSED"
        gained = sorted(set(rb["hits_full"]) - set(ra["hits_full"]))
        lost = sorted(set(ra["hits_full"]) - set(rb["hits_full"]))
        delta = "; ".join(
            p for p in ("+" + ", ".join(gained) if gained else "",
                        "-" + ", ".join(lost) if lost else "") if p
        )
        print(f"  case {rb['id']:>2}  {da} -> {db}  {flag}   {delta}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=list(CONFIGS), default=None)
    ap.add_argument("--compare", action="store_true", help="all configs side by side")
    ap.add_argument("--verbose", action="store_true", help="per-case diff vs count (with --compare)")
    args = ap.parse_args()

    cases = json.loads(EVAL_FILE.read_text())["cases"]
    bucket_index = load_bucket_index()

    if args.compare:
        results = {name: evaluate(name, bucket_index, cases) for name in CONFIGS}
        for name in CONFIGS:
            print(f"=== {name} ===")
            print_summary(results[name])
            print()
        if args.verbose:
            for name in ("count_salience", "count_salience_dedup", "salience"):
                print_diff(results["count"], results[name])
        return

    name = args.config
    if name is None:
        name = next(
            (n for n, (s, r, d) in CONFIGS.items()
             if s == SCORING_MODE and r == RANK_MODE and d == DEDUP_SIMILAR_PROMPTS),
            None,
        )
        if name is None:
            print(f"configured SCORING_MODE={SCORING_MODE!r} + RANK_MODE={RANK_MODE!r} "
                  f"+ DEDUP_SIMILAR_PROMPTS={DEDUP_SIMILAR_PROMPTS!r} "
                  f"is not a named config; pass --config explicitly")
            return
    res = evaluate(name, bucket_index, cases)
    print(f"=== eval: {len(cases)} cases ===")
    print_summary(res)


if __name__ == "__main__":
    main()
