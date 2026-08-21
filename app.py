#!/usr/bin/env python3
"""
app.py -- minimal test UI for the CHOICE bucket-matching pipeline.

Not part of the CLAUDE_CODE_BUILD_BRIEF.md phases (0-6) -- those cover the
matching engine itself. This is a thin Flask wrapper around get_tooltip.py
so testers can type a master prompt in a browser and see the ranked
tooltip lines, instead of using the CLI. Choice Forge integration (the
real production UI) is separate, later work -- this is for internal
testing only.

Usage:
    python3 app.py
    # then open http://127.0.0.1:5000
"""

from flask import Flask, render_template, request

from match_buckets import load_bucket_index, match_buckets
from get_tooltip import rank_buckets, render_tooltip

app = Flask(__name__)

# Load once at startup -- lemmatizing all 80 buckets on every request would
# be wasteful (see match_buckets.py's docstring on why bucket_index is a
# pass-in param).
_bucket_index = load_bucket_index()


@app.route("/", methods=["GET", "POST"])
def index():
    master_prompt = ""
    ranked = []
    if request.method == "POST":
        master_prompt = request.form.get("master_prompt", "").strip()
        if master_prompt:
            match_results = match_buckets(master_prompt, bucket_index=_bucket_index)
            ranked = rank_buckets(match_results, _bucket_index, master_prompt=master_prompt)
            lines = render_tooltip(ranked)
            for r, line in zip(ranked, lines):
                r["tooltip_line"] = line

    return render_template("index.html", master_prompt=master_prompt, ranked=ranked)


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
