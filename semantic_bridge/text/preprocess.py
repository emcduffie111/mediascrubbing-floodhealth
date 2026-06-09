"""Text preprocessing helpers."""

from __future__ import annotations

import re

from semantic_bridge.types import DocumentMap


def preprocess_text(text: str, custom_stopwords: set[str] | None = None) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = text.split()
    if custom_stopwords:
        normalized_stopwords = {word.strip().lower() for word in custom_stopwords if word.strip()}
        tokens = [token for token in tokens if token not in normalized_stopwords]
    return " ".join(tokens)


def preprocess_documents(
    documents: DocumentMap,
    custom_stopwords: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    doc_names = list(documents.keys())
    processed_docs = [preprocess_text(text, custom_stopwords=custom_stopwords) for text in documents.values()]
    return processed_docs, doc_names

