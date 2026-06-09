"""Human-readable helpers for filtering and mapping the UCSD science backbone.

The important design choice is:

    documents/topics -> filtered science backbone -> topic/domain mappings

The helpers here avoid hand-written case-study seed terms by default, but they
still allow optional ``extra_terms`` when a corpus is sparse or when an
instructor wants to bias a demo.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any, Iterable

import pandas as pd

from semantic_bridge.text.topics import topic_display_name


DEFAULT_STOPWORDS = {
    # English/function words
    "about", "above", "across", "after", "again", "against", "also", "among",
    "and", "are", "because", "been", "before", "being", "below", "between",
    "both", "but", "can", "could", "did", "does", "doing", "done", "during",
    "each", "few", "for", "from", "had", "has", "have", "having", "into",
    "its", "itself", "may", "more", "most", "not", "off", "our", "out",
    "over", "own", "same", "should", "such", "than", "that", "the", "their",
    "then", "there", "these", "they", "this", "those", "through", "under",
    "use", "used", "using", "was", "were", "when", "where", "which", "while",
    "with", "within", "would", "you", "your",
    # common paper/report words that should not drive science-domain filtering
    "abstract", "analysis", "approach", "article", "authors", "based", "case",
    "data", "dataset", "datasets", "document", "documents", "figure", "figures",
    "finding", "findings", "introduction", "method", "methods", "model",
    "models", "paper", "papers", "report", "reports", "research", "result",
    "results", "section", "study", "table", "tables", "text",
}


def clean_term(value: Any) -> str:
    """Normalize a word or phrase for matching."""
    text = " ".join(str(value).lower().replace("_", " ").split())
    text = re.sub(r"[^a-z0-9\- ]+", "", text)
    return text.strip()


def term_tokens(value: Any) -> set[str]:
    """Tokenize a term or label into useful matching tokens."""
    cleaned = clean_term(value)
    tokens = set(re.findall(r"\b[a-z][a-z0-9\-]{2,}\b", cleaned))
    return {token for token in tokens if token not in DEFAULT_STOPWORDS}


def unique_in_order(values: Iterable[Any]) -> list[str]:
    """Return cleaned unique terms while keeping first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        term = clean_term(value)
        if not term or term in seen:
            continue
        seen.add(term)
        out.append(term)
    return out


def document_to_text(document: Any) -> str:
    """Extract text from document shapes used in the Day 2 notebook."""
    if document is None:
        return ""

    if isinstance(document, str):
        return document

    if isinstance(document, dict):
        for key in ("text", "content", "page_content", "body", "raw_text"):
            value = document.get(key)
            if value:
                return str(value)
        return " ".join(str(value) for value in document.values() if value is not None)

    for attr in ("page_content", "text", "content", "body"):
        value = getattr(document, attr, None)
        if value:
            return str(value)

    return str(document)


def collect_topic_terms(topics_info: dict[str, dict[str, Any]] | None) -> list[str]:
    """Collect topic labels, descriptions, and keywords from discovered topics."""
    if not topics_info:
        return []

    terms: list[str] = []
    for topic_id, topic_data in topics_info.items():
        terms.extend(topic_data.get("keywords", []) or [])
        terms.extend(topic_data.get("terms", []) or [])
        terms.append(topic_display_name(topic_data))
        terms.append(topic_data.get("description", ""))
        terms.append(topic_id)

    return unique_in_order(terms)


def collect_corpus_terms(
    documents: Iterable[Any] | None,
    *,
    processed_docs: Iterable[str] | None = None,
    top_n: int = 100,
    stopwords: set[str] | None = None,
) -> list[str]:
    """Extract high-frequency words and two-word phrases from the loaded corpus."""
    if documents is None and processed_docs is None:
        return []

    stop = stopwords or DEFAULT_STOPWORDS
    if processed_docs:
        text = "\n".join(str(item) for item in processed_docs if item).lower()
    else:
        text = "\n".join(document_to_text(doc) for doc in documents).lower()

    tokens = re.findall(r"\b[a-z][a-z0-9\-]{2,}\b", text)
    tokens = [token for token in tokens if token not in stop and not token.isdigit()]

    unigram_counts = Counter(tokens)
    bigram_counts = Counter(
        f"{tokens[i]} {tokens[i + 1]}"
        for i in range(len(tokens) - 1)
        if tokens[i] not in stop and tokens[i + 1] not in stop
    )

    phrases = [term for term, _ in bigram_counts.most_common(max(10, top_n // 2))]
    words = [term for term, _ in unigram_counts.most_common(top_n)]
    return unique_in_order([*phrases, *words])[:top_n]


def collect_case_terms(
    *,
    topics_info: dict[str, dict[str, Any]] | None = None,
    documents: Iterable[Any] | None = None,
    processed_docs: Iterable[str] | None = None,
    extra_terms: Iterable[str] | None = None,
    max_corpus_terms: int = 100,
) -> dict[str, list[str]]:
    """Collect all terms used to filter the science backbone."""
    topic_terms = collect_topic_terms(topics_info)
    corpus_terms = collect_corpus_terms(documents, processed_docs=processed_docs, top_n=max_corpus_terms)
    hint_terms = unique_in_order(extra_terms or [])

    all_terms = unique_in_order([*topic_terms, *corpus_terms, *hint_terms])
    all_terms = [term for term in all_terms if len(term) > 2 and term not in DEFAULT_STOPWORDS]

    return {
        "topic_terms": topic_terms,
        "corpus_terms": corpus_terms,
        "extra_terms": hint_terms,
        "all_terms": all_terms,
    }


def node_search_terms(domain: str, node: dict[str, Any]) -> list[str]:
    """Return normalized searchable terms for one science-backbone node."""
    values: list[Any] = [domain]
    values.extend(node.get("subdisciplines", []) or [])
    values.extend(node.get("terms", []) or [])
    values.extend(node.get("keywords", []) or [])
    values.extend(node.get("matched_filter_terms", []) or [])
    return unique_in_order(value for value in values if value is not None)


def node_search_text(domain: str, node: dict[str, Any]) -> str:
    """Build searchable text for one science-backbone domain."""
    return " | ".join(node_search_terms(domain, node))


def score_terms_against_node(
    query_terms: Iterable[str],
    domain: str,
    node: dict[str, Any],
) -> tuple[float, list[str]]:
    """Score a term list against one science-backbone node.

    The scoring mechanism combines two strategies to ensure robust matching:
    1. Phrase Containment: Direct matches of the query term (or multi-word phrase) 
       within the node's text. Multi-word matches are weighted higher (3.0) than 
       unigrams (1.5).
    2. Token Overlap: Matches between individual words (tokens) in the query 
       and the node. This serves as a fallback for partial matches, with 
       diminishing returns for multiple token matches to prevent over-weighting 
       broad categories.

    Returns a tuple of (total_score, unique_matched_terms).
    """
    searchable_terms = node_search_terms(domain, node)
    searchable_text = " | ".join(searchable_terms)
    searchable_tokens = set()
    for value in searchable_terms:
        searchable_tokens.update(term_tokens(value))

    score = 0.0
    matches: list[str] = []

    for raw_term in query_terms:
        term = clean_term(raw_term)
        if len(term) <= 2 or term in DEFAULT_STOPWORDS:
            continue

        tokens = term_tokens(term)
        if not tokens:
            continue

        phrase_match = term in searchable_text
        overlap = tokens & searchable_tokens

        if phrase_match:
            score += 3.0 if " " in term else 1.5
            matches.append(term)
        elif overlap:
            # Token overlap is weaker than phrase match, but it prevents
            # obvious cases from being missed.
            score += min(1.25, 0.35 * len(overlap))
            matches.extend(sorted(overlap))

    return score, unique_in_order(matches)


def filter_subdisciplines(
    subdisciplines: Iterable[str],
    case_terms: Iterable[str],
    *,
    keep_top_n: int = 30,
) -> list[str]:
    """Keep subdisciplines that visibly match case terms.

    If no subdiscipline labels match directly, keep a small readable sample so
    a retained domain is not empty.
    """
    terms = [clean_term(term) for term in case_terms if len(clean_term(term)) > 2]
    term_token_sets = [(term, term_tokens(term)) for term in terms]

    scored: list[tuple[float, str]] = []

    for sub in subdisciplines or []:
        sub_clean = clean_term(sub)
        sub_tokens = term_tokens(sub_clean)
        score = 0.0
        for term, tokens in term_token_sets:
            if term in sub_clean or sub_clean in term:
                score += 2.0
            elif tokens & sub_tokens:
                score += 0.5 * len(tokens & sub_tokens)
        if score > 0:
            scored.append((score, str(sub)))

    if scored:
        scored.sort(key=lambda item: (-item[0], item[1].lower()))
        return [sub for _, sub in scored[:keep_top_n]]

    return list(subdisciplines or [])[: min(keep_top_n, 10)]


def filter_science_backbone_for_case(
    science_backbone: dict[str, dict[str, Any]],
    *,
    topics_info: dict[str, dict[str, Any]] | None = None,
    documents: Iterable[Any] | None = None,
    processed_docs: Iterable[str] | None = None,
    extra_terms: Iterable[str] | None = None,
    keep_top_domains: int = 6,
    keep_top_subdisciplines: int = 30,
    min_domain_score: float = 1.0,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Filter the full UCSD backbone down to the current document/case study.

    This function performs an automated reduction of a large science backbone 
    (like the 13-discipline UCSD Map of Science) to a subset relevant to the 
    specific corpus being analyzed. It uses keywords and labels from discovered 
    topics as well as high-frequency terms from the document text to score and 
    rank backbone domains and subdisciplines.
    """
    term_groups = collect_case_terms(
        topics_info=topics_info,
        documents=documents,
        processed_docs=processed_docs,
        extra_terms=extra_terms,
    )
    case_terms = term_groups["all_terms"]

    scored_domains: list[tuple[float, str, dict[str, Any], list[str]]] = []
    for domain, node in science_backbone.items():
        score, matches = score_terms_against_node(case_terms, domain, node)
        if score >= min_domain_score:
            kept = deepcopy(node)
            kept["subdisciplines"] = filter_subdisciplines(
                kept.get("subdisciplines", []),
                case_terms,
                keep_top_n=keep_top_subdisciplines,
            )
            kept["filter_score"] = round(score, 3)
            kept["matched_filter_terms"] = matches
            kept["source"] = kept.get("source", "UCSD Map of Science")
            scored_domains.append((score, domain, kept, matches))

    scored_domains.sort(key=lambda item: (-item[0], item[1].lower()))
    if keep_top_domains:
        scored_domains = scored_domains[:keep_top_domains]

    filtered = {domain: node for score, domain, node, matches in scored_domains}
    debug = {
        **term_groups,
        "domain_scores": [
            {
                "domain": domain,
                "score": round(score, 3),
                "matches": matches[:12],
                "kept_subdisciplines": len(node.get("subdisciplines", [])),
            }
            for score, domain, node, matches in scored_domains
        ],
    }
    return filtered, debug


def topic_query_terms(topic_id: str, topic_data: dict[str, Any]) -> list[str]:
    """Collect matching terms for one topic."""
    terms: list[Any] = []
    terms.extend(topic_data.get("keywords", []) or [])
    terms.extend(topic_data.get("terms", []) or [])
    terms.append(topic_display_name(topic_data))
    terms.append(topic_data.get("description", ""))
    terms.append(topic_id)
    return unique_in_order(terms)


def rank_topic_domains(
    topic_id: str,
    topic_data: dict[str, Any],
    science_backbone: dict[str, dict[str, Any]],
    *,
    min_score: float = 0.25,
) -> list[dict[str, Any]]:
    """Rank all science-backbone domains for one discovered topic."""
    query_terms = topic_query_terms(topic_id, topic_data)
    ranked: list[dict[str, Any]] = []

    for domain, node in science_backbone.items():
        score, matches = score_terms_against_node(query_terms, domain, node)
        if score >= min_score:
            ranked.append(
                {
                    "domain": domain,
                    "score": round(score, 3),
                    "matched_terms": matches,
                }
            )

    ranked.sort(key=lambda item: (-item["score"], item["domain"].lower()))
    return ranked


def make_topic_mappings_from_backbone(
    topics_info: dict[str, dict[str, Any]],
    science_backbone: dict[str, dict[str, Any]],
    *,
    domains_per_topic: int = 3,
    min_score: float = 0.25,
    include_low_score_fallback: bool = True,
) -> list[dict[str, Any]]:
    """Map discovered topics to the filtered science backbone.

    Each topic can now carry a ranked list of candidate domains, not just one
    primary domain. This fixes the visualization problem where the topic layer
    appears to cover only two domains even though the filtered backbone kept more.

    The primary domain remains the best-scoring domain for compatibility with
    existing notebook cells.
    """
    mappings: list[dict[str, Any]] = []

    for topic_id, topic_data in topics_info.items():
        ranked = rank_topic_domains(
            topic_id,
            topic_data,
            science_backbone,
            min_score=min_score,
        )

        if not ranked and include_low_score_fallback and science_backbone:
            # Use the strongest weak match so the topic is not orphaned.
            fallback_scores = []
            query_terms = topic_query_terms(topic_id, topic_data)
            for domain, node in science_backbone.items():
                score, matches = score_terms_against_node(query_terms, domain, node)
                fallback_scores.append((score, domain, matches))
            fallback_scores.sort(key=lambda item: (-item[0], item[1].lower()))
            if fallback_scores:
                score, domain, matches = fallback_scores[0]
                ranked = [{"domain": domain, "score": round(score, 3), "matched_terms": matches}]

        kept_ranked = ranked[:domains_per_topic]
        primary = kept_ranked[0] if kept_ranked else {"domain": "General", "score": 0, "matched_terms": []}
        secondary = kept_ranked[1] if len(kept_ranked) > 1 else None

        mappings.append(
            {
                "topic": topic_id,
                "topic_label": topic_display_name(topic_data),
                "keywords": ", ".join(topic_data.get("keywords", [])[:5]),
                "primary_domain": primary["domain"],
                "secondary_domain": secondary["domain"] if secondary else None,
                "candidate_domains": kept_ranked,
                "candidate_domain_labels": ", ".join(item["domain"] for item in kept_ranked),
                "matched_terms": ", ".join(primary.get("matched_terms", [])[:10]),
                "mapping_score": primary.get("score", 0),
            }
        )

    return mappings


def topic_mappings_table(topic_mappings: list[dict[str, Any]]) -> pd.DataFrame:
    """Small display helper for notebooks."""
    columns = [
        "topic",
        "topic_label",
        "keywords",
        "primary_domain",
        "secondary_domain",
        "candidate_domain_labels",
        "mapping_score",
        "matched_terms",
    ]
    return pd.DataFrame(topic_mappings).reindex(columns=columns)


def domain_coverage_table(
    science_backbone: dict[str, dict[str, Any]],
    topic_mappings: list[dict[str, Any]],
) -> pd.DataFrame:
    """Summarize which filtered science domains are covered by topic mappings."""
    rows = []
    for domain, node in science_backbone.items():
        primary_topics = []
        any_topics = []

        for mapping in topic_mappings:
            if mapping.get("primary_domain") == domain:
                primary_topics.append(mapping.get("topic_label") or mapping.get("topic"))

            candidate_domains = {
                item.get("domain")
                for item in mapping.get("candidate_domains", [])
                if isinstance(item, dict)
            }
            if domain in candidate_domains or mapping.get("secondary_domain") == domain:
                any_topics.append(mapping.get("topic_label") or mapping.get("topic"))

        rows.append(
            {
                "domain": domain,
                "filter_score": node.get("filter_score"),
                "matched_filter_terms": ", ".join((node.get("matched_filter_terms") or [])[:10]),
                "primary_topic_count": len(primary_topics),
                "candidate_topic_count": len(set(any_topics + primary_topics)),
                "primary_topics": "; ".join(primary_topics),
                "candidate_topics": "; ".join(sorted(set(any_topics + primary_topics))),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["candidate_topic_count", "primary_topic_count", "filter_score"],
        ascending=[False, False, False],
    )
