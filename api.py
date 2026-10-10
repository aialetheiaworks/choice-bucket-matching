#!/usr/bin/env python3
"""
api.py -- REST API for the CHOICE bucket-matching pipeline.

This is the production integration point for the Choice Forge frontend
(see CLAUDE.md's "next step" note) -- unlike app.py/gradio_app.py/
streamlit_app.py (internal testing UIs with their own HTML), this is a
plain JSON API meant to be called cross-origin from a separate frontend
codebase.

Loads the bucket index once at startup, same as app.py -- calling
get_tooltip() per-request would re-lemmatize all 80 buckets on every
call (~14s, see CLAUDE.md's Phase 5 notes), so this calls match_buckets()
-> rank_buckets() -> render_tooltip() directly against the cached index
instead.

Usage:
    uvicorn api:app --reload          # local dev, http://127.0.0.1:8000
    # docs at http://127.0.0.1:8000/docs
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from match_buckets import load_bucket_index, match_buckets
from get_tooltip import rank_buckets, render_tooltip

app = FastAPI(title="CHOICE Bucket Matching API", version="1.0.0")

# Comma-separated list of allowed frontend origins, e.g.
# "https://app.choiceforge.com,http://localhost:3000". Defaults to "*"
# for local development -- tighten this before pointing a real frontend
# domain at a deployed instance.
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allowed_origins == "*" else _allowed_origins.split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Load once at startup -- see match_buckets.py's docstring on why
# bucket_index is a pass-in param rather than reloaded per call.
_bucket_index = load_bucket_index()


class TooltipRequest(BaseModel):
    master_prompt: str = Field(..., min_length=1, description="The Choice Forge master prompt to match against the bucket library.")
    max_lines: int | None = Field(None, ge=1, le=9, description=(
        "Display cap for an end-user screen. When set, at most this many lines come back and at most "
        "2 of them are technology/engineering buckets. Unset = the full ranked list (what the eval scores)."))


# Engineering buckets that crowded out business angles for small-business owners
# (CHOICE_FEEDBACK_2026-10-01.md: "app"/"platform" pulled in backlog, scalability, ...).
TECH_BUCKETS = {"technology", "technology_feasibility", "data", "data_ai", "ai_ml", "security",
                "scalability", "reliability", "performance", "backlog", "monitoring", "knowledge",
                "accessibility"}
MAX_TECH_SHOWN = 2
# Tier-1/tier-2 pairs that say the same thing in different depth; show one of each.
SAME_ANGLE = [{"technology", "technology_feasibility"}, {"data", "data_ai", "ai_ml"}]


def for_display(ranked, max_lines):
    """Keep the engine's order, but cap technology buckets, show one bucket per
    SAME_ANGLE group, and cap the list length. A presentation step only:
    rank_buckets() and the eval are untouched."""
    shown, tech = [], 0
    for r in ranked:
        if any(r["id"] in g and g & {x["id"] for x in shown} for g in SAME_ANGLE):
            continue
        if r["id"] in TECH_BUCKETS:
            if tech == MAX_TECH_SHOWN:
                continue
            tech += 1
        shown.append(r)
    return shown[:max_lines]


class RankedBucket(BaseModel):
    id: str
    name: str
    tier: int
    prompt: str
    score: float  # primary ranking score (int count, unless salience scoring)
    count_score: int = 0  # distinct matched vocabulary terms
    salience_score: float = 0.0  # those terms' summed dependency-salience weight
    matched_terms: list[str]
    tooltip_line: str


class TooltipResponse(BaseModel):
    tooltip_lines: list[str]
    ranked: list[RankedBucket]


@app.get("/health")
def health():
    return {"status": "ok", "buckets_loaded": len(_bucket_index)}


@app.post("/tooltip", response_model=TooltipResponse)
def tooltip(req: TooltipRequest):
    master_prompt = req.master_prompt.strip()
    if not master_prompt:
        raise HTTPException(status_code=400, detail="master_prompt must not be empty")

    match_results = match_buckets(master_prompt, bucket_index=_bucket_index)
    ranked = rank_buckets(match_results, _bucket_index, master_prompt=master_prompt)
    if req.max_lines:
        ranked = for_display(ranked, req.max_lines)
    lines = render_tooltip(ranked)
    for r, line in zip(ranked, lines):
        r["tooltip_line"] = line

    return TooltipResponse(tooltip_lines=lines, ranked=ranked)
