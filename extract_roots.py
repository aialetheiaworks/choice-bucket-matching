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

# en_core_web_sm lemmatizes "data" to "datum" when it tags the token as
# plural (NNS -- its default outside a noun-modifier position), but leaves
# it as "data" when tagged singular (NN, e.g. directly before another noun
# as in "data strategy"). Business phrasing uses "data" as an uncountable
# mass noun and never means literal "datum", so force a single lemma
# regardless of position -- otherwise the same surface word silently
# extracts/matches inconsistently depending on sentence position (found in
# Phase 6 eval, see PHASE6_EVAL_RESULTS.md).
IRREGULAR_LEMMAS = {"data": "data"}

# spaCy's en_core_web_sm flags "go" as a stopword (verified: is_stop=True on
# every occurrence, regardless of context/POS -- it's a static lexeme flag,
# not context-sensitive). That silently broke every "go to market"/
# "go-to-market" vocabulary phrase: with "go" dropped, both lemmatized down
# to just "market", indistinguishable from the plain Market bucket (found
# 2026-09-01 chasing a stakeholder bug report about exactly this phrase).
# Never drop these specific words as stopwords, on either the vocabulary
# side (match_buckets.py's _lemmatize_term) or the input side (below).
NEVER_STOP = {"go"}

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(MODEL_NAME)
    return _nlp


def _lemma_of(token):
    return IRREGULAR_LEMMAS.get(token.text.lower(), token.lemma_.lower())


def _is_content_token(token):
    """Same filtering rule match_buckets.py's _lemmatize_term applies to
    vocabulary terms (drop stopwords/punct/space, no POS restriction) --
    kept in lockstep so a phrase built from the master prompt is directly
    comparable to how bucket vocabulary phrases were lemmatized."""
    if token.is_punct or token.is_space:
        return False
    if token.is_stop and token.text.lower() not in NEVER_STOP:
        return False
    return True


def extract_roots(master_prompt, phrase_vocab=None):
    """Return a deduplicated set of lemma root words + root phrases
    extracted from the master prompt.

    `phrase_vocab` (optional): the set of known multi-word bucket-vocabulary
    phrases (lemmatized, space-joined -- see match_buckets.py's
    _lemmatize_term), used to scan the prompt for real vocabulary phrases
    instead of guessing at generic noun-chunk boundaries. Longest phrase
    wins at each position, and once a phrase matches, its constituent words
    are consumed -- they don't also surface as separate single-word roots.
    This replaced a noun-chunk-based approach (2026-09-01, stakeholder
    feedback) that had two problems: it only caught noun-phrase-shaped
    text, missing verb-containing vocabulary idioms like "go to market"
    entirely, and it never suppressed sub-words, so a matched phrase like
    "target market" always coexisted with a separate "market" root,
    diluting a specific match into also triggering unrelated broader
    buckets. Called without `phrase_vocab` (e.g. this module's standalone
    CLI), only single-word roots are extracted -- fine for that diagnostic
    use, since Phase 2 scoring only cares about vocabulary-driven phrases
    anyway."""
    nlp = _get_nlp()
    doc = nlp(master_prompt)
    roots = set()

    content_tokens = [t for t in doc if _is_content_token(t)]
    lemmas = [_lemma_of(t) for t in content_tokens]
    consumed = [False] * len(content_tokens)

    if phrase_vocab:
        max_len = max((len(p.split()) for p in phrase_vocab), default=1)
        n = len(lemmas)
        i = 0
        while i < n:
            for length in range(min(max_len, n - i), 1, -1):
                candidate = " ".join(lemmas[i:i + length])
                if candidate in phrase_vocab:
                    roots.add(candidate)
                    for j in range(i, i + length):
                        consumed[j] = True
                    i += length
                    break
            else:
                i += 1

    for idx, token in enumerate(content_tokens):
        if consumed[idx]:
            continue
        if token.pos_ not in KEEP_POS:
            continue
        lemma = lemmas[idx].strip()
        if lemma:
            roots.add(lemma)

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
