#!/usr/bin/env python3
"""
extract_roots.py

Phase 1 of the CHOICE bucket-matching pipeline (see CLAUDE_CODE_BUILD_BRIEF.md):
extracts a deduplicated set of root words and root phrases from the Choice
Forge master prompt, ready to be matched against bucket_library.json's
synonym lists in Phase 2.

No word vectors / semantic similarity here, by design (see the brief's
"Decision already made" note) -- lemmatization + POS filtering + noun-chunk
extraction only, on en_core_web_sm.

Negation is not detected or suppressed here (per the 2026-08-18 decision in
the build brief): a negated phrase's content words extract and match the
same as any other phrase.

**2026-08-19 workflow change:** the pipeline now takes the Choice Forge
master prompt as its only input. The separate raw user query (and the
query-vs-prompt source weighting it existed to support) has been dropped --
Choice Forge's master prompt is the single source of truth going into this
pipeline.

Usage:
    python3 extract_roots.py "<master prompt>"
    # or: from extract_roots import extract_roots
"""

import sys

import spacy

MODEL_NAME = "en_core_web_sm"
KEEP_POS = {"NOUN", "PROPN", "VERB", "ADJ"}

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(MODEL_NAME)
    return _nlp


def extract_roots(master_prompt):
    """Return a deduplicated set of lemma root words + root noun-chunk
    phrases extracted from the master prompt."""
    nlp = _get_nlp()
    doc = nlp(master_prompt)
    roots = set()

    for token in doc:
        if token.is_stop or token.is_punct or token.is_space:
            continue
        if token.pos_ not in KEEP_POS:
            continue
        lemma = token.lemma_.lower().strip()
        if lemma:
            roots.add(lemma)

    for chunk in doc.noun_chunks:
        # Drop leading determiners/possessives ("the", "our") so "our value
        # proposition" contributes the phrase "value proposition", matching
        # how multi-word bucket names/synonyms are stored (no articles).
        content_tokens = [t for t in chunk if not (t.is_stop or t.is_punct)]
        if len(content_tokens) < 2:
            continue  # single-word chunks are already covered by the token loop above
        phrase = " ".join(t.lemma_.lower() for t in content_tokens).strip()
        if phrase:
            roots.add(phrase)

    return roots


def main():
    if len(sys.argv) != 2:
        print('Usage: python3 extract_roots.py "<master prompt>"')
        sys.exit(1)
    roots = extract_roots(sys.argv[1])
    print(f"Extracted {len(roots)} root words/phrases:")
    for r in sorted(roots):
        print(f"  {r}")


if __name__ == "__main__":
    main()
