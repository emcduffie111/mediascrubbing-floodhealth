"""SVO mapping helpers."""

from __future__ import annotations

from collections import Counter

import pandas as pd
from nltk.tokenize import sent_tokenize


def create_svo_mappings(
    documents: dict[str, str],
    svo_vocabulary: dict[str, dict[str, object]],
    min_keyword_words: int = 2,
    allow_single_word_keywords: set[str] | None = None,
) -> list[dict[str, str]]:
    mappings = []
    allowed_singletons = {keyword.strip().lower() for keyword in (allow_single_word_keywords or set()) if keyword.strip()}
    for doc_name, text in documents.items():
        text_lower = text.lower()
        for svo_name, svo_info in svo_vocabulary.items():
            for keyword in svo_info["keywords"]:
                normalized_keyword = " ".join(keyword.lower().split())
                keyword_word_count = len(normalized_keyword.split())
                if keyword_word_count < min_keyword_words and normalized_keyword not in allowed_singletons:
                    continue
                if keyword in text_lower:
                    context = ""
                    for sentence in sent_tokenize(text):
                        if keyword in sentence.lower():
                            context = sentence
                            break
                    mappings.append(
                        {
                            "natural_language_term": keyword,
                            "scientific_variable": svo_name,
                            "standard_name": svo_info["standard_name"],
                            "units": svo_info["units"],
                            "domain": svo_info["domain"],
                            "data_source": svo_info["data_source"],
                            "source_document": doc_name,
                            "context": context[:150],
                        }
                    )
    return mappings


def deduplicate_svo_mappings(svo_mappings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique_mappings = []
    seen = set()
    for mapping in svo_mappings:
        key = (mapping["natural_language_term"], mapping["scientific_variable"])
        if key not in seen:
            seen.add(key)
            unique_mappings.append(mapping)
    return unique_mappings


def svo_table(unique_mappings: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(unique_mappings)


def domain_counts(unique_mappings: list[dict[str, str]]) -> dict[str, int]:
    return dict(Counter(mapping["domain"] for mapping in unique_mappings))

