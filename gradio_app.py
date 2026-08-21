#!/usr/bin/env python3
"""
gradio_app.py -- Hugging Face Spaces test UI for the CHOICE bucket-matching
pipeline (Gradio SDK, no Docker/payment verification required for a free
Space, unlike app.py's Flask+Docker version which needs a verified account).

Same pipeline as app.py -- extract_roots.py -> match_buckets.py ->
get_tooltip.py -- just a different front end. Not part of the phased
build brief; internal testing only.

Local run:
    python3 gradio_app.py
Hugging Face Spaces: set sdk: gradio and app_file: gradio_app.py in
README.md's front matter (already set), then push this repo to the Space.
"""

import gradio as gr

from match_buckets import load_bucket_index, match_buckets
from get_tooltip import rank_buckets, render_tooltip

_bucket_index = load_bucket_index()

EXAMPLE = (
    "Increase annual sales of premium office chairs by 30% within the "
    "next 12 months by targeting small and medium-sized businesses in "
    "India, while operating within a marketing budget of ₹20 lakh "
    "and without expanding the sales team."
)


def get_tooltip_markdown(master_prompt):
    master_prompt = (master_prompt or "").strip()
    if not master_prompt:
        return "_Enter a master prompt above and click Submit._"

    match_results = match_buckets(master_prompt, bucket_index=_bucket_index)
    ranked = rank_buckets(match_results, _bucket_index, master_prompt=master_prompt)
    if not ranked:
        return "_No buckets matched._"

    lines = render_tooltip(ranked)
    out = []
    for i, (r, line) in enumerate(zip(ranked, lines), start=1):
        terms = ", ".join(f"`{t}`" for t in r["matched_terms"]) or "—"
        out.append(
            f"**{i}. {line}**\n\n"
            f"&nbsp;&nbsp;&nbsp;&nbsp;tier {r['tier']} · score {r['score']} · matched: {terms}"
        )
    return "\n\n---\n\n".join(out)


demo = gr.Interface(
    fn=get_tooltip_markdown,
    inputs=gr.Textbox(
        label="Master prompt",
        placeholder="Paste a Choice Forge master prompt here...",
        lines=5,
    ),
    outputs=gr.Markdown(label="Tooltip output"),
    title="CHOICE Bucket Matching — Test UI",
    description=(
        "Internal test UI for the CHOICE root-word bucket matching "
        "pipeline. Paste a master prompt and see the ranked tooltip "
        "lines the matching engine would surface."
    ),
    examples=[[EXAMPLE]],
)

if __name__ == "__main__":
    demo.launch()
