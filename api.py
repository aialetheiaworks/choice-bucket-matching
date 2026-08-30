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


class RankedBucket(BaseModel):
    id: str
    name: str
    tier: int
    prompt: str
    score: int
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
    lines = render_tooltip(ranked)
    for r, line in zip(ranked, lines):
        r["tooltip_line"] = line

    return TooltipResponse(tooltip_lines=lines, ranked=ranked)
