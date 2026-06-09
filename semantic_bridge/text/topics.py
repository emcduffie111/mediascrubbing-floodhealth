"""Topic modeling helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer


def discover_topics(
    processed_docs: list[str],
    n_topics: int,
    max_vocabulary: int,
    topic_keyword_count: int = 8,
    custom_stopwords: set[str] | None = None,
) -> dict[str, object]:
    combined_stopwords: str | list[str] = "english"
    if custom_stopwords:
        sklearn_stopwords = TfidfVectorizer(stop_words="english").get_stop_words()
        user_stopwords = {word.strip().lower() for word in custom_stopwords if word.strip()}
        combined_stopwords = sorted(sklearn_stopwords.union(user_stopwords))
    vectorizer = TfidfVectorizer(
        max_features=max_vocabulary,
        stop_words=combined_stopwords,
        ngram_range=(1, 2),
    )
    doc_term_matrix = vectorizer.fit_transform(processed_docs)
    feature_names = vectorizer.get_feature_names_out()

    lda_model = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
    )
    doc_topic_dist = lda_model.fit_transform(doc_term_matrix)

    topics_info = {}
    for idx, topic in enumerate(lda_model.components_):
        top_indices = topic.argsort()[-topic_keyword_count:][::-1]
        top_words = [feature_names[i] for i in top_indices]
        topic_id = f"Topic {idx + 1}"
        topics_info[topic_id] = {
            "label": f"{topic_id}: {', '.join(top_words[:3])}",
            "keywords": top_words,
        }

    return {
        "vectorizer": vectorizer,
        "lda_model": lda_model,
        "doc_topic_dist": doc_topic_dist,
        "feature_names": feature_names,
        "topics_info": topics_info,
    }


def topic_display_name(topic_info: dict[str, Any]) -> str:
    return topic_info.get("human_label") or topic_info["label"]


def build_topic_summary(topics_info: dict[str, dict[str, object]], doc_topic_dist, top_words_display: int) -> pd.DataFrame:
    summary_data = []
    for topic_num, info in topics_info.items():
        topic_index = int(topic_num.split()[1]) - 1
        summary_data.append(
            {
                "Topic": topic_num,
                "Label": topic_display_name(info),
                "Description": info.get("description", ""),
                "Top Keywords": ", ".join(info["keywords"][:top_words_display]),
                "Avg Coverage": f"{doc_topic_dist[:, topic_index].mean():.1%}",
            }
        )
    return pd.DataFrame(summary_data)


def build_topic_distribution_frame(doc_topic_dist, doc_names: list[str], n_topics: int) -> pd.DataFrame:
    return pd.DataFrame(
        doc_topic_dist,
        columns=[f"Topic {i + 1}" for i in range(n_topics)],
        index=[Path(name).stem for name in doc_names],
    )

