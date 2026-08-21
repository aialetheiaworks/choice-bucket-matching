#!/usr/bin/env python3
"""
match_buckets.py

Phase 2 of the CHOICE bucket-matching pipeline (see CLAUDE_CODE_BUILD_BRIEF.md):
scores every bucket in bucket_library.json (both tiers, 80 buckets total)
against the root words/phrases Phase 1 (extract_roots.py) pulled from the
Choice Forge master prompt.

Matching is lemma-to-lemma set comparison, not substring matching -- each
bucket's name + synonyms are lemmatized once at load time (via spaCy, the
same pipeline extract_roots.py uses) so both sides compare on equal footing.

Scoring: score = number of distinct matched terms (bucket name or synonym).
**2026-08-19 workflow change:** the old PROMPT_WEIGHT/QUERY_WEIGHT split no
longer applies -- the pipeline takes a single master-prompt input now (the
separate raw user query was dropped), so there's no second source to weight
against. Every matched term counts equally.

This module does NOT do tier deduplication, tie-breaking, top-5 selection,
or the fewer-than-5/zero-match fallback -- that's Phase 3 (ranking),
layered on top of the per-bucket scores this module returns.

Usage:
    python3 match_buckets.py "<master prompt>"
    # or: from match_buckets import match_buckets, load_bucket_index
"""

import json
import sys
from pathlib import Path

import spacy

from extract_roots import extract_roots, IRREGULAR_LEMMAS

BUCKET_FILE = Path(__file__).parent / "bucket_library.json"
MODEL_NAME = "en_core_web_sm"

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(MODEL_NAME)
    return _nlp


def _lemmatize_term(nlp, term):
    """Lemmatize a bucket name or synonym the same way extract_roots.py
    lemmatizes extracted phrases (lowercased, space-joined lemmas, content
    words only) so the two sides are comparable lemma-for-lemma. Falls
    back to a naive lowercase if spaCy strips every token (e.g. a term
    that's entirely a stopword), so a term is never silently dropped from
    the index."""
    doc = nlp(term)
    lemmas = [
        IRREGULAR_LEMMAS.get(t.text.lower(), t.lemma_.lower())
        for t in doc
        if not (t.is_stop or t.is_punct or t.is_space)
    ]
    if not lemmas:
        return term.lower().strip()
    return " ".join(lemmas)


def load_bucket_index():
    """Load bucket_library.json and return a list of bucket dicts, each
    augmented with a lemmatized 'match_terms' set (bucket name + every
    synonym, lemmatized). Built fresh from the JSON file every call --
    cheap enough (80 buckets, ~970 synonyms total) that callers don't need
    to manage caching themselves."""
    nlp = _get_nlp()
    data = json.loads(BUCKET_FILE.read_text())
    buckets = [{**b, "tier": 1} for b in data["tier_1_buckets"]] + [
        {**b, "tier": 2} for b in data["tier_2_buckets"]
    ]
    for b in buckets:
        terms = {_lemmatize_term(nlp, b["name"])}
        terms.update(_lemmatize_term(nlp, s) for s in b.get("synonyms", []))
        b["match_terms"] = {t for t in terms if t}
    return buckets


def score_bucket(bucket, roots):
    """Score one bucket against the extracted root set. Returns
    (score, matched_terms) -- matched_terms is every distinct term (bucket
    name or synonym) that matched a root extracted from the master prompt;
    score is just its count now that there's a single input source to
    match against."""
    matched_terms = bucket["match_terms"] & roots
    return len(matched_terms), matched_terms


def match_buckets(master_prompt, bucket_index=None):
    """Score every bucket (both tiers) against the master prompt.
    Returns a list of dicts (one per bucket that matched at least one
    term -- a zero-score bucket carries no signal and Phase 3 handles the
    zero-match case separately), sorted by score descending:
        {id, name, tier, prompt, score, matched_terms}
    Pass a pre-built bucket_index (from load_bucket_index()) to avoid
    re-lemmatizing all 80 buckets on every call in a hot loop (e.g. Phase 6's
    eval harness against 15-20 prompts)."""
    if bucket_index is None:
        bucket_index = load_bucket_index()

    roots = extract_roots(master_prompt)

    results = []
    for bucket in bucket_index:
        score, matched_terms = score_bucket(bucket, roots)
        if score <= 0:
            continue
        results.append({
            "id": bucket["id"],
            "name": bucket["name"],
            "tier": bucket["tier"],
            "prompt": bucket["prompt"],
            "score": score,
            "matched_terms": sorted(matched_terms),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def main():
    if len(sys.argv) != 2:
        print('Usage: python3 match_buckets.py "<master prompt>"')
        sys.exit(1)
    results = match_buckets(sys.argv[1])
    print(f"{len(results)} buckets matched at least one term:\n")
    for r in results:
        print(f"  [{r['score']}] T{r['tier']} {r['name']} ({r['id']})")
        print(f"        matched: {', '.join(r['matched_terms'])}")


if __name__ == "__main__":
    main()
