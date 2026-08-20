#!/usr/bin/env python3
"""
merge_reviewed_synonyms.py

Takes the human-reviewed bucket_synonyms_review.csv (after you've filled in
'approve (y/n)' for each candidate term) and writes the approved terms into
bucket_library.json's "synonyms" field for each bucket.

Usage:
    python3 merge_reviewed_synonyms.py
"""

import csv
import json
from pathlib import Path

BUCKET_FILE = Path(__file__).parent / "bucket_library.json"
REVIEW_CSV = Path(__file__).parent / "bucket_synonyms_review.csv"
OUTPUT_FILE = Path(__file__).parent / "bucket_library.json"  # overwrite in place


def main():
    data = json.loads(BUCKET_FILE.read_text())
    by_id = {}
    for b in data["tier_1_buckets"] + data["tier_2_buckets"]:
        by_id[b["id"]] = b
        b["synonyms"] = []  # reset before merging approved terms

    approved_count = 0
    with open(REVIEW_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            approve = row.get("approve (y/n)", "").strip().lower()
            if approve != "y":
                continue
            bucket_id = row["bucket_id"]
            term = row["candidate_term"].strip()
            if bucket_id in by_id and term:
                by_id[bucket_id]["synonyms"].append(term)
                approved_count += 1

    BUCKET_FILE.write_text(json.dumps(data, indent=2))
    print(f"Merged {approved_count} approved synonyms into {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
