#!/usr/bin/env python3
"""
streamlit_app.py -- Streamlit Community Cloud test UI for the CHOICE
bucket-matching pipeline. Same pipeline as app.py/gradio_app.py
(extract_roots.py -> match_buckets.py -> get_tooltip.py), different front
end -- Streamlit Community Cloud deploys from a GitHub repo for free and
runs a real Python backend, unlike Hugging Face's free Static-only tier.

Not part of the phased build brief; internal testing only.

Local run:
    streamlit run streamlit_app.py
Streamlit Community Cloud: connect this repo's GitHub remote at
share.streamlit.io and point it at this file.
"""

import streamlit as st

from match_buckets import load_bucket_index, match_buckets
from get_tooltip import rank_buckets, render_tooltip

EXAMPLE = (
    "Increase annual sales of premium office chairs by 30% within the "
    "next 12 months by targeting small and medium-sized businesses in "
    "India, while operating within a marketing budget of ₹20 lakh "
    "and without expanding the sales team."
)


@st.cache_resource
def get_bucket_index():
    return load_bucket_index()


st.set_page_config(page_title="CHOICE Bucket Matching — Test UI", page_icon="🧭")
st.title("CHOICE Bucket Matching")
st.caption(
    "Internal test UI for the CHOICE root-word bucket matching pipeline. "
    "Paste a Choice Forge master prompt and see the ranked tooltip lines "
    "the matching engine would surface."
)

master_prompt = st.text_area(
    "Master prompt",
    placeholder="Paste a Choice Forge master prompt here...",
    height=140,
)

col1, col2 = st.columns([1, 5])
with col1:
    submitted = st.button("Get tooltip", type="primary")
with col2:
    if st.button("Use example"):
        master_prompt = EXAMPLE
        submitted = True

if submitted and master_prompt.strip():
    bucket_index = get_bucket_index()
    match_results = match_buckets(master_prompt, bucket_index=bucket_index)
    ranked = rank_buckets(match_results, bucket_index, master_prompt=master_prompt)

    if not ranked:
        st.info("No buckets matched.")
    else:
        lines = render_tooltip(ranked)
        for i, (r, line) in enumerate(zip(ranked, lines), start=1):
            with st.container(border=True):
                st.markdown(f"**{i}. {line}**")
                terms = ", ".join(f"`{t}`" for t in r["matched_terms"]) or "—"
                st.caption(f"tier {r['tier']} · score {r['score']} · matched: {terms}")
elif submitted:
    st.warning("Enter a master prompt first.")
