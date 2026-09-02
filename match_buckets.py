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

Scoring (SCORING_MODE):
- "count"    -- score = number of distinct matched terms (bucket name or
               synonym). Every matched term counts 1.0. This is the
               original behaviour, unchanged.
- "salience" -- score = sum of the dependency-salience weights (0-1) of the
               matched terms, from extract_roots_salience(): a term matched
               via the statement's main subject/verb counts ~1.0, one
               matched only through a word deep in a subordinate clause
               counts a fraction of that. Continuous scores, so the
               boundary ties that force get_tooltip.py's MAX_N cap to cut
               genuine matches (see PHASE6_EVAL_RESULTS.md crowding writeup)
               mostly dissolve, and a bucket triggered only by an
               incidental generic verb ("improve", "reduce") no longer
               ties a bucket that is what the statement is actually about.
               Added 2026-09-02, adapted from a stakeholder sample script.

Both modes return the same fields; "count" is exactly "salience" with every
weight pinned to 1.0, so the two share one code path.

**2026-08-19 workflow change:** the old PROMPT_WEIGHT/QUERY_WEIGHT split no
longer applies -- the pipeline takes a single master-prompt input now (the
separate raw user query was dropped), so there's no second source to weight
against.

This module does NOT do tier deduplication, tie-breaking, top-5 selection,
or the fewer-than-5/zero-match fallback -- that's Phase 3 (ranking),
layered on top of the per-bucket scores this module returns.

Usage:
    python3 match_buckets.py "<master prompt>"
    # or: from match_buckets import match_buckets, load_bucket_index
"""

import hashlib
import json
import pickle
import sys
from pathlib import Path

import spacy

from extract_roots import extract_roots_salience, IRREGULAR_LEMMAS, NEVER_STOP

BUCKET_FILE = Path(__file__).parent / "bucket_library.json"
CACHE_FILE = Path(__file__).parent / "bucket_index_cache.pkl"
CACHE_VERSION = 2  # bump if _lemmatize_term()/load_bucket_index() logic changes
MODEL_NAME = "en_core_web_sm"

# Which score match_buckets() reports as the primary `score` field:
#   "count"    -- distinct matched terms (original behaviour)
#   "salience" -- summed dependency-salience weights of those terms
# Every result carries BOTH count_score and salience_score regardless; this
# only picks which one lands in `score` (used by the logger, the CLI, and
# get_tooltip's MAX_N tie-group cutoff). Ranking order is chosen separately
# by get_tooltip.RANK_MODE. Default "count": the salience signal is used
# only as get_tooltip's tie-breaker ("count_salience"), which the eval
# shows keeps recall while improving which buckets win contested slots
# (PHASE6_EVAL_RESULTS.md 2026-09-02). Set to "salience" only alongside
# RANK_MODE="salience".
SCORING_MODE = "count"

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
        if not (t.is_punct or t.is_space)
        and not (t.is_stop and t.text.lower() not in NEVER_STOP)
    ]
    if not lemmas:
        return term.lower().strip()
    return " ".join(lemmas)


def _cache_key():
    """Ties the cache to both the vocabulary file's exact content and this
    module's lemmatization logic -- either changing invalidates it."""
    return f"{hashlib.sha256(BUCKET_FILE.read_bytes()).hexdigest()}:v{CACHE_VERSION}"


def load_bucket_index():
    """Load bucket_library.json and return a list of bucket dicts, each
    augmented with a lemmatized 'match_terms' set (bucket name + every
    synonym, lemmatized).

    Lemmatizing all ~8,210 vocabulary terms through spaCy on every call
    used to be "cheap enough" when the vocabulary was ~970 terms, but
    after the 2026-08-25 stakeholder vocabulary merge (8.5x growth) it
    measured ~14s locally and, on a slow-CPU host (e.g. Render's free
    tier), took ~5 minutes -- unacceptable for a cold API start. Now
    cached to disk (bucket_index_cache.pkl): a hash of bucket_library.json
    (+ CACHE_VERSION, for logic changes) keys the cache, so it's rebuilt
    automatically whenever the vocabulary or lemmatization logic changes,
    and reused as a fast pickle load otherwise. This also fixes the CLI's
    per-invocation reload cost, not just the API's cold start."""
    cache_key = _cache_key()
    if CACHE_FILE.exists():
        try:
            cached_key, buckets = pickle.loads(CACHE_FILE.read_bytes())
            if cached_key == cache_key:
                return buckets
        except Exception:
            pass  # corrupt/incompatible cache -- fall through and rebuild

    nlp = _get_nlp()
    data = json.loads(BUCKET_FILE.read_text())
    buckets = [{**b, "tier": 1} for b in data["tier_1_buckets"]] + [
        {**b, "tier": 2} for b in data["tier_2_buckets"]
    ]
    for b in buckets:
        terms = {_lemmatize_term(nlp, b["name"])}
        terms.update(_lemmatize_term(nlp, s) for s in b.get("synonyms", []))
        b["match_terms"] = {t for t in terms if t}

    try:
        CACHE_FILE.write_bytes(pickle.dumps((cache_key, buckets)))
    except OSError:
        pass  # caching is an optimization, not a requirement

    return buckets


def score_bucket(bucket, root_weights):
    """Score one bucket against the extracted roots. `root_weights` maps
    every extracted root -> its dependency-salience weight (0-1). Returns
    (count_score, salience_score, term_weights):
      - count_score    -- number of distinct bucket terms (name/synonym)
                          that matched (the original score)
      - salience_score -- sum of those matched terms' salience weights
      - term_weights   -- {matched term -> its salience weight}
    Phase 2 picks which of the two scores is primary per SCORING_MODE;
    both travel on every result so Phase 3 can rank by either (or use one
    to break ties in the other)."""
    term_weights = {
        term: root_weights[term] for term in bucket["match_terms"] & root_weights.keys()
    }
    return len(term_weights), sum(term_weights.values()), term_weights


def match_buckets(master_prompt, bucket_index=None, scoring=None):
    """Score every bucket (both tiers) against the master prompt.
    Returns a list of dicts (one per bucket that matched at least one
    term -- a zero-score bucket carries no signal and Phase 3 handles the
    zero-match case separately), sorted by score descending:
        {id, name, tier, prompt, score, matched_terms, term_weights}
    `score` is an int in "count" mode and a float in "salience" mode;
    `term_weights` maps each matched term to the weight it contributed, so
    Phase 3's tier-dedup can re-sum a merged bucket's score without
    re-running the matcher, and the log/CLI can show why a bucket ranked
    where it did.

    `scoring` -- "count" | "salience", defaults to the module's
    SCORING_MODE. Pass a pre-built bucket_index (from load_bucket_index())
    to avoid re-lemmatizing all 80 buckets on every call in a hot loop
    (e.g. Phase 6's eval harness against 15-20 prompts).

    Builds the known-phrase vocabulary (every multi-word match_term across
    all buckets) fresh from bucket_index each call and hands it to Phase 1
    so root extraction can do vocabulary-driven longest-match phrase
    detection -- see extract_roots()'s docstring. Deriving it from
    bucket_index's already-lemmatized match_terms (rather than
    re-lemmatizing bucket_library.json separately) guarantees the phrase
    dictionary and the vocabulary being matched against can never drift
    out of sync."""
    if bucket_index is None:
        bucket_index = load_bucket_index()
    if scoring is None:
        scoring = SCORING_MODE

    if scoring not in ("count", "salience"):
        raise ValueError(f"unknown scoring mode: {scoring!r}")

    phrase_vocab = {
        term for bucket in bucket_index for term in bucket["match_terms"] if " " in term
    }
    # One parse, both scores: extract_roots_salience() returns the same
    # roots as extract_roots() plus a salience weight each, so the count
    # score is just len() of the matched subset -- no reason to run the
    # non-salience path separately.
    root_weights = extract_roots_salience(master_prompt, phrase_vocab=phrase_vocab)

    results = []
    for bucket in bucket_index:
        count_score, salience_score, term_weights = score_bucket(bucket, root_weights)
        if count_score <= 0:
            continue
        primary = salience_score if scoring == "salience" else count_score
        results.append({
            "id": bucket["id"],
            "name": bucket["name"],
            "tier": bucket["tier"],
            "prompt": bucket["prompt"],
            "score": round(primary, 4),
            "count_score": count_score,
            "salience_score": round(salience_score, 4),
            "matched_terms": sorted(term_weights),
            "term_weights": {t: round(w, 4) for t, w in term_weights.items()},
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def main():
    if len(sys.argv) != 2:
        print('Usage: python3 match_buckets.py "<master prompt>"')
        sys.exit(1)
    results = match_buckets(sys.argv[1])
    print(f"{len(results)} buckets matched at least one term (SCORING_MODE={SCORING_MODE!r}):\n")
    for r in results:
        print(f"  [{r['score']:>6}] T{r['tier']} {r['name']} ({r['id']})")
        matched = ", ".join(
            f"{t} ({w})" for t, w in sorted(r["term_weights"].items(), key=lambda kv: -kv[1])
        )
        print(f"        matched: {matched}")


if __name__ == "__main__":
    main()
