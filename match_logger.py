#!/usr/bin/env python3
"""
match_logger.py

Phase 5 of the CHOICE bucket-matching pipeline (see CLAUDE_CODE_BUILD_BRIEF.md):
persists every pipeline run so match quality can be debugged/tuned against
real usage later, and so zero-/low-match queries can be found as evidence for
whether the spaCy semantic-similarity fallback (explicitly out of scope for
v1) is ever actually worth building -- see the build brief's Phase 5 section.

Appends one JSON object per line to LOG_FILE (JSONL) -- no DB, consistent
with the rest of this build's local-file-only approach; readable with plain
`tail`/`jq`, no extra dependency. Called from `rank_buckets()` in
get_tooltip.py, the one chokepoint every front end (CLI, Flask, Gradio,
Streamlit) already passes through, so no per-front-end wiring beyond passing
`master_prompt` through is needed.

Known limitation: on Streamlit Community Cloud specifically, the filesystem
is ephemeral across redeploys/restarts (though it persists across requests
within one running instance) -- fine for local/CLI/Flask use and for
within-session data on the live deployed app, but this file will not
accumulate a durable long-term log there. Revisit (e.g. write to a hosted
DB/sheet instead) once/if that durability is actually needed.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent / "match_log.jsonl"


def log_match(master_prompt, match_results, ranked, log_file=LOG_FILE):
    """Append one record of a pipeline run.

    `match_results` is match_buckets()'s raw, pre-ranking output (every
    bucket that matched at least one term, before dedup/top-5/fallback) --
    used so zero-/low-match queries are flagged correctly even when
    rank_buckets() pads the display with the CORE_BUCKETS fallback.
    `ranked` is what was actually shown to the user.

    Never raises on a logging failure (e.g. read-only filesystem) -- a
    broken log must not break the matching pipeline itself; the caller
    still gets its tooltip either way.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "master_prompt": master_prompt,
        "raw_match_count": len(match_results),
        "is_zero_match": len(match_results) == 0,
        "is_low_match": len(match_results) == 1,
        "matched": [
            {
                "id": r["id"],
                "name": r["name"],
                "tier": r["tier"],
                "score": r["score"],
                "matched_terms": r["matched_terms"],
            }
            for r in match_results
        ],
        "shown": [
            {"id": r["id"], "name": r["name"], "tier": r["tier"], "score": r["score"]}
            for r in ranked
        ],
    }
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass
