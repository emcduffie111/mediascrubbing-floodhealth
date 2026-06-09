"""Decision component extraction helpers."""

from __future__ import annotations

from copy import deepcopy
from html import unescape
from pathlib import Path
import re
from typing import Any

import pandas as pd

from semantic_bridge.constants import DEFAULT_COMPONENT_PATTERNS
from semantic_bridge.constants import DEFAULT_COMPONENT_SEED_PHRASES


def _normalized_token_set(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 2}


def _lexical_similarity(candidate: Any, reference: Any) -> float:
    candidate_tokens = _normalized_token_set(getattr(candidate, "text", ""))
    reference_tokens = _normalized_token_set(getattr(reference, "text", ""))
    if not candidate_tokens or not reference_tokens:
        return 0.0
    overlap = candidate_tokens.intersection(reference_tokens)
    union = candidate_tokens.union(reference_tokens)
    return len(overlap) / len(union)


def _safe_similarity(candidate: Any, reference: Any) -> float:
    # Avoid spaCy W007 from small models (e.g., en_core_web_sm) that do not ship vectors.
    vocab = getattr(candidate, "vocab", None)
    vectors_length = getattr(vocab, "vectors_length", 0) if vocab is not None else 0
    candidate_has_vector = bool(getattr(candidate, "has_vector", False))
    reference_has_vector = bool(getattr(reference, "has_vector", False))
    if vectors_length <= 0 or not candidate_has_vector or not reference_has_vector:
        return _lexical_similarity(candidate, reference)

    try:
        score = float(candidate.similarity(reference))
    except Exception:
        return _lexical_similarity(candidate, reference)
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def _build_seed_docs(nlp: Any, component_seeds: dict[str, list[str]]) -> dict[str, list[Any]]:
    seed_docs: dict[str, list[Any]] = {component: [] for component in component_seeds}
    for component, seeds in component_seeds.items():
        for seed in seeds:
            try:
                seed_docs[component].append(nlp(seed))
            except Exception:
                continue
    return seed_docs


def _context_paragraph(document_text: str, sentence_text: str) -> str:
    sentence = str(sentence_text or "").strip()
    if not sentence:
        return ""

    paragraphs = [block.strip() for block in re.split(r"\n\s*\n+", str(document_text or "")) if block.strip()]
    if not paragraphs:
        return sentence

    for paragraph in paragraphs:
        if sentence in paragraph:
            return paragraph

    sentence_lower = sentence.lower()
    for paragraph in paragraphs:
        if sentence_lower in paragraph.lower():
            return paragraph

    return sentence


def extract_decision_components(
    documents,
    nlp,
    patterns: dict[str, list[str]] | None = None,
    component_seeds: dict[str, list[str]] | None = None,
    keyword_weight: float = 0.45,
    semantic_weight: float = 0.55,
):
    component_patterns = deepcopy(patterns or DEFAULT_COMPONENT_PATTERNS)
    component_seed_map = deepcopy(component_seeds or DEFAULT_COMPONENT_SEED_PHRASES)
    seed_docs = _build_seed_docs(nlp, component_seed_map)
    components = {
        "goals": [],
        "objectives": [],
        "variables": [],
        "constraints": [],
        "indicators": [],
    }

    for doc_name, text in documents.items():
        doc = nlp(text)
        for sent in doc.sents:
            sent_text = sent.text.lower()
            for comp_type, keywords in component_patterns.items():
                if any(keyword in sent_text for keyword in keywords):
                    for chunk in sent.noun_chunks:
                        if len(chunk.text.split()) >= 2:
                            semantic_score = 0.0
                            for seed_doc in seed_docs.get(comp_type, []):
                                semantic_score = max(semantic_score, _safe_similarity(chunk, seed_doc))
                            confidence = keyword_weight + (semantic_weight * semantic_score)
                            components[comp_type].append(
                                {
                                    "text": chunk.text,
                                    "source": doc_name,
                                    "context": _context_paragraph(text, sent.text),
                                    "confidence": round(confidence, 4),
                                }
                            )

    for comp_type in components:
        best_by_text: dict[str, dict[str, Any]] = {}
        for item in components[comp_type]:
            existing = best_by_text.get(item["text"])
            if existing is None or item["confidence"] > existing["confidence"]:
                best_by_text[item["text"]] = item
        ranked = sorted(best_by_text.values(), key=lambda value: value["confidence"], reverse=True)
        components[comp_type] = ranked[:50]
    return components


def component_counts(decision_components: dict[str, list[dict[str, str]]]) -> dict[str, int]:
    return {key: len(value) for key, value in decision_components.items()}


def component_table(decision_components: dict[str, list[dict[str, str]]]) -> pd.DataFrame:
    rows = []
    for comp_type, items in decision_components.items():
        for item in items:
            rows.append(
                {
                    "component_type": comp_type,
                    "text": item["text"],
                    "source": item["source"],
                    "context": item["context"],
                }
            )
    return pd.DataFrame(rows)


def _clean_display_text(value: Any, max_chars: int | None = None) -> str:
    text = str(value or "")
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def _display_source_name(source: Any) -> str:
    stem = Path(str(source or "")).stem
    if not stem:
        return ""
    name = stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip()


def human_readable_component_table(
    components_df: pd.DataFrame,
    prefer_readable_text: bool = True,
    max_context_chars: int | None = None,
) -> pd.DataFrame:
    """Return a cleaned, presentation-ready component table for notebook display."""

    table = components_df.copy()

    base_text_column = "text"
    if prefer_readable_text and "readable_text" in table.columns:
        base_text_column = "readable_text"

    table["Component Type"] = table.get("component_type", "").map(
        {
            "goals": "Goal",
            "objectives": "Objective",
            "variables": "Decision Variable",
            "constraints": "Constraint",
            "indicators": "Indicator",
        }
    ).fillna(table.get("component_type", ""))
    table["Decision Component"] = table.get(base_text_column, "").map(_clean_display_text)
    table["Source Document"] = table.get("source", "").map(_display_source_name)
    table["Evidence Context"] = table.get("context", "").map(lambda value: _clean_display_text(value, max_context_chars))

    presentation_columns = [
        "Component Type",
        "Decision Component",
        "Source Document",
        "Evidence Context",
    ]
    if "readable_rationale" in table.columns:
        table["Rewrite Note"] = table["readable_rationale"].map(_clean_display_text)
        presentation_columns.append("Rewrite Note")
    if "confidence" in table.columns:
        table["Confidence"] = table["confidence"]
        presentation_columns.append("Confidence")

    return table[presentation_columns]
