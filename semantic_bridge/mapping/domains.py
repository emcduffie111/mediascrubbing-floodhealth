"""Topic-to-domain mapping helpers."""

from __future__ import annotations

from semantic_bridge.constants import DEFAULT_DOMAIN_KEYWORDS, default_science_backbone, default_svo_vocabulary
from semantic_bridge.text.topics import topic_display_name


def map_topics_to_domains(
    topics_info: dict[str, dict[str, object]],
    domain_keywords: dict[str, list[str]] | None = None,
) -> list[dict[str, object]]:
    keywords_by_domain = domain_keywords or DEFAULT_DOMAIN_KEYWORDS
    mappings = []
    for topic_id, topic_data in topics_info.items():
        topic_keywords = set(" ".join(topic_data["keywords"]).lower().split())
        domain_scores = {}
        for domain, keywords in keywords_by_domain.items():
            matches = topic_keywords.intersection(set(keywords))
            if matches:
                domain_scores[domain] = len(matches)
        relevant = sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)[:2]
        mappings.append(
            {
                "topic": topic_id,
                "topic_label": topic_display_name(topic_data),
                "keywords": ", ".join(topic_data["keywords"][:5]),
                "primary_domain": relevant[0][0] if relevant else "General",
                "secondary_domain": relevant[1][0] if len(relevant) > 1 else None,
            }
        )
    return mappings


__all__ = ["default_science_backbone", "default_svo_vocabulary", "map_topics_to_domains"]

