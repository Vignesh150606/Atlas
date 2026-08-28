import re
from typing import List
from app.retrieval.retrieval_service import extract_keywords
from app.models.document import Document

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def extractive_summary(text: str, max_sentences: int = 3) -> str:
    """Deterministic, frequency-based extractive summary (a light version
    of the classic Luhn algorithm): score each sentence by how many
    significant (non-stopword) keywords it contains, take the top-N
    highest-scoring sentences, then re-order them back to their original
    position in the text so the summary still reads coherently.

    No LLM call, no embeddings - pure term-frequency statistics, consistent
    with tools being deterministic and provider-independent.
    """
    text = text.strip()
    if not text:
        return ""

    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    keywords = extract_keywords(text, max_keywords=30)
    keyword_set = set(keywords)

    scored: List[tuple] = []
    for idx, sentence in enumerate(sentences):
        words = re.findall(r"[A-Za-z0-9']+", sentence.lower())
        score = sum(1 for w in words if w in keyword_set)
        # Mild length normalization so one long sentence stuffed with
        # keywords doesn't dominate purely on word count.
        normalized = score / max(len(words), 1) ** 0.5
        scored.append((normalized, idx, sentence))

    top = sorted(scored, key=lambda t: t[0], reverse=True)[:max_sentences]
    top_in_order = sorted(top, key=lambda t: t[1])
    return " ".join(t[2] for t in top_in_order)


def multi_document_summary(documents: List[Document], sentences_per_document: int = 2) -> str:
    """Phase 9 / "knowledge summaries": a synthesized summary spanning
    *several* ranked documents, not just one - e.g. "summarize what I know
    about Project Atlas" when that spans three separate uploaded documents.

    Deliberately still just extractive_summary applied per-document and
    concatenated with attribution, not a second summarization algorithm -
    reuses the same deterministic, no-LLM, no-embeddings approach rather
    than introducing a different one for the multi-document case. Each
    document gets fewer sentences than a single-document summary would
    (`sentences_per_document`, default 2 vs extractive_summary's default 3)
    so the combined result stays a genuine overview rather than growing
    linearly with document count.
    """
    if not documents:
        return ""
    parts = []
    for document in documents:
        summary = extractive_summary(document.content, max_sentences=sentences_per_document)
        if summary:
            parts.append(f"From \"{document.title}\": {summary}")
    return "\n\n".join(parts)
