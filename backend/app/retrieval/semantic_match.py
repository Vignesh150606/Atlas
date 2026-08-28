"""Phase 9: shared "semantic-like" text relevance scoring.

ATLAS deliberately has no vector database or embeddings (see
docs/Roadmap.md - vector search is an explicit, deferred future phase).
Before Phase 9, both `app/retrieval/ranking.py` (memories) and
`app/knowledge/ranking.py` (documents) computed keyword relevance the same
way - independently - as a raw count of exact substring hits divided by
keyword count. That has two real weaknesses:

1. It's all-or-nothing per keyword: "class" scores 0 against "classes" or
   "classroom" even though they're obviously related.
2. Every keyword is weighted equally, so a keyword that appears in nearly
   every memory (weak signal) counts the same as one that appears in almost
   none (strong signal).

This module fixes both without adding a vector dependency: light stemming
(strip common suffixes) for morphological near-misses, plus a corpus-aware
term-weighting pass callers can optionally supply. It's still pure
term-frequency statistics over the candidate pool already gathered by
RetrievalService/KnowledgeRetrievalService - "semantic-like" in the sense
the mission brief asks for, not an embedding similarity.

Both ranking modules import `relevance_score` from here instead of each
defining their own `_keyword_relevance_score` - this also removes the
near-duplicate logic DRY was already being violated by.
"""
import re
from collections import Counter
from typing import Iterable, List, Sequence

# Suffixes stripped for a cheap, deterministic stem - ordered longest-first
# so "classes" strips to "class" (not "classe"). This is intentionally not a
# real stemmer (no Porter/Snowball dependency) - just enough to catch the
# most common English plural/verb-form near-misses without over-stripping
# short words into unrelated stems.
_SUFFIXES = ("ing", "edly", "ed", "es", "s")
_MIN_STEM_LEN = 3


def stem(word: str) -> str:
    """Best-effort, deterministic light stem: 'classes' -> 'class',
    'running' -> 'runn' (good enough for equality comparison against
    another stemmed word - it doesn't need to be a real root)."""
    word = word.lower()
    for suffix in _SUFFIXES:
        if not word.endswith(suffix) or len(word) - len(suffix) < _MIN_STEM_LEN:
            continue
        # A bare trailing "s" preceded by another "s" ("class", "grass",
        # "pass") is part of the root, not a plural marker - stripping it
        # would turn "class" into "clas", which then no longer matches the
        # correctly-stemmed "classes" -> "class". Only "es"/other suffixes
        # are exempt from this guard since they already consume the double-s.
        if suffix == "s" and word.endswith("ss"):
            continue
        return word[: -len(suffix)]
    return word


def _tokens(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def build_term_weights(corpus_texts: Iterable[str]) -> "Counter[str]":
    """Corpus-aware term weighting (an inverse-document-frequency-flavored
    signal, computed over whatever candidate pool is already in memory -
    not a persistent index): terms that appear in fewer candidate items get
    a higher weight than terms that appear in almost all of them. Optional -
    every caller of `relevance_score` can omit this and get plain
    (stemmed) overlap scoring instead.
    """
    doc_freq: Counter = Counter()
    total_docs = 0
    for text in corpus_texts:
        total_docs += 1
        seen_stems = {stem(t) for t in _tokens(text)}
        doc_freq.update(seen_stems)
    if total_docs == 0:
        return Counter()
    import math
    weights: Counter = Counter()
    for term, freq in doc_freq.items():
        # +1 smoothing so a term appearing in every candidate still gets a
        # small positive (not zero) weight rather than vanishing entirely.
        weights[term] = math.log((total_docs + 1) / (freq + 1)) + 1.0
    return weights


def relevance_score(
    haystack: str,
    keywords: Sequence[str],
    term_weights: "Counter[str] | None" = None,
) -> float:
    """Normalized [0, 1] relevance of `haystack` to `keywords`.

    Exact substring hits score full credit per keyword (preserves the
    original behavior exactly for the common case); a keyword with no exact
    hit but whose *stem* appears in the haystack scores partial credit
    (0.6) instead of zero, e.g. "class" vs "classroom notes" - this is the
    "semantic-like" improvement over Phase 8's pure substring counting.
    When `term_weights` is supplied, each keyword's contribution is scaled
    by its weight (rarer terms across the candidate pool count for more)
    before normalizing, rather than every keyword counting equally.
    """
    if not keywords:
        return 0.0

    haystack_lower = haystack.lower()
    haystack_tokens = _tokens(haystack)
    haystack_stems = {stem(t) for t in haystack_tokens}

    total_weight = 0.0
    earned = 0.0
    for kw in keywords:
        kw_lower = kw.lower()
        weight = term_weights.get(stem(kw_lower), 1.0) if term_weights else 1.0
        total_weight += weight

        if kw_lower in haystack_lower:
            earned += weight
        elif stem(kw_lower) in haystack_stems:
            earned += weight * 0.6

    if total_weight <= 0:
        return 0.0
    return min(1.0, earned / total_weight)
