#!/usr/bin/env python3
"""
generate_synonyms.py

Builds a first-pass candidate synonym/keyword list for every bucket in
bucket_library.json, by combining:
  1. WordNet (via nltk)      — formal synonym sets
  2. Datamuse API (free, no key) — related / "means like" words
  3. Merriam-Webster Thesaurus API (optional, needs a free API key)

Output: a review-ready CSV (bucket_synonyms_review.csv) with one row per
candidate term per bucket, so a human can approve/reject before the terms
get baked into bucket_library.json's "synonyms" field.

This does NOT decide matching logic or thresholds — it only builds the
candidate word lists. Run this once (or whenever buckets change), review
the CSV, then feed the approved terms back into bucket_library.json.

Usage:
    pip install nltk requests
    python3 -m nltk.downloader wordnet omw-1.4   # one-time, needs network
    export MERRIAM_WEBSTER_API_KEY=xxxx           # optional
    python3 generate_synonyms.py
"""

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

try:
    from nltk.corpus import wordnet as wn
except ImportError:
    wn = None

BUCKET_FILE = Path(__file__).parent / "bucket_library.json"
OUTPUT_CSV = Path(__file__).parent / "bucket_synonyms_review.csv"

MW_API_KEY = os.environ.get("MERRIAM_WEBSTER_API_KEY", "").strip()
DATAMUSE_URL = "https://api.datamuse.com/words"
MW_URL = "https://www.dictionaryapi.com/api/v3/references/thesaurus/json/{word}?key={key}"

REQUEST_TIMEOUT = 6
SLEEP_BETWEEN_CALLS = 0.15  # be polite to the free Datamuse API


def clean_term(term):
    term = term.lower().strip()
    term = re.sub(r"[_\-]+", " ", term)
    term = re.sub(r"[^a-z0-9 &/]", "", term)
    return term.strip()


def wordnet_synonyms(phrase):
    """Return a set of synonym lemmas from WordNet for a word or short phrase."""
    if wn is None:
        return set()
    out = set()
    # WordNet works best on single words; also try each word in a multi-word bucket name.
    words = phrase.split()
    candidates = [phrase.replace(" ", "_")] + words
    for w in candidates:
        try:
            for syn in wn.synsets(w):
                for lemma in syn.lemmas():
                    name = lemma.name().replace("_", " ")
                    if name.lower() != phrase.lower():
                        out.add(name.lower())
        except Exception:
            continue
    return out


def datamuse_related(phrase):
    """Pull both tight synonyms (rel_syn) and looser related words (ml=) from Datamuse."""
    out = set()
    queries = [
        {"rel_syn": phrase},
        {"ml": phrase},
    ]
    for params in queries:
        try:
            r = requests.get(DATAMUSE_URL, params={**params, "max": 15}, timeout=REQUEST_TIMEOUT)
            if r.ok:
                for item in r.json():
                    out.add(item["word"].lower())
        except Exception as e:
            print(f"    [datamuse warn] {phrase}: {e}", file=sys.stderr)
        time.sleep(SLEEP_BETWEEN_CALLS)
    return out


def merriam_webster_synonyms(phrase):
    if not MW_API_KEY:
        return set()
    out = set()
    try:
        url = MW_URL.format(word=phrase.replace(" ", "%20"), key=MW_API_KEY)
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.ok:
            data = r.json()
            for entry in data:
                if isinstance(entry, dict):
                    for syn_group in entry.get("meta", {}).get("syns", []):
                        out.update(s.lower() for s in syn_group)
    except Exception as e:
        print(f"    [merriam-webster warn] {phrase}: {e}", file=sys.stderr)
    return out


def build_candidates(bucket_name, prompt_text):
    """Combine all three sources for a bucket's name AND its prompt's key nouns."""
    all_terms = {}

    def add(term, source):
        term = clean_term(term)
        if not term or term == bucket_name.lower():
            return
        all_terms.setdefault(term, set()).add(source)

    for term in wordnet_synonyms(bucket_name):
        add(term, "wordnet")
    for term in datamuse_related(bucket_name):
        add(term, "datamuse")
    for term in merriam_webster_synonyms(bucket_name):
        add(term, "merriam-webster")

    return all_terms


def main():
    if wn is None:
        print("WARNING: nltk/wordnet not available — skipping WordNet source.", file=sys.stderr)
    if not MW_API_KEY:
        print("INFO: MERRIAM_WEBSTER_API_KEY not set — skipping Merriam-Webster source.", file=sys.stderr)

    data = json.loads(BUCKET_FILE.read_text())
    all_buckets = [
        {**b, "tier": 1} for b in data["tier_1_buckets"]
    ] + [
        {**b, "tier": 2} for b in data["tier_2_buckets"]
    ]

    rows = []
    for i, bucket in enumerate(all_buckets, 1):
        name = bucket["name"]
        print(f"[{i}/{len(all_buckets)}] {name}")
        candidates = build_candidates(name, bucket["prompt"])
        if not candidates:
            rows.append({
                "bucket_id": bucket["id"], "bucket_name": name, "tier": bucket["tier"],
                "candidate_term": "", "sources": "", "approve (y/n)": "",
            })
        for term, sources in sorted(candidates.items()):
            rows.append({
                "bucket_id": bucket["id"],
                "bucket_name": name,
                "tier": bucket["tier"],
                "candidate_term": term,
                "sources": "|".join(sorted(sources)),
                "approve (y/n)": "",  # human fills this in during review
            })

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "bucket_id", "bucket_name", "tier", "candidate_term", "sources", "approve (y/n)"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} candidate rows written to {OUTPUT_CSV}")
    print("Next: open the CSV, mark 'approve (y/n)' for each row, then run")
    print("merge_reviewed_synonyms.py to fold approved terms back into bucket_library.json.")


if __name__ == "__main__":
    main()
