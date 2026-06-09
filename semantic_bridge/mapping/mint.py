"""MINT vocabulary and model recommendation helpers."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any
from urllib.parse import unquote

import requests

from semantic_bridge.text.topics import topic_display_name


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.startswith("http"):
            normalized = unquote(normalized.rstrip("/").split("/")[-1])
        return [normalized]
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_coerce_string_list(item))
        return values
    if isinstance(value, dict):
        for key in ("label", "name", "value", "id"):
            nested = value.get(key)
            values = _coerce_string_list(nested)
            if values:
                return values
    return []


def _first_nonempty(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        values = _coerce_string_list(value)
        if values:
            return values[0]
    return ""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _humanize_identifier(text: str) -> str:
    cleaned = text.replace("_", " ").replace("~", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.isupper():
        return cleaned.title()
    return cleaned


def _identifier_tail(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = unquote(value)
    value = value.split("#")[-1]
    value = value.split("?")[0]
    value = value.rstrip("/")
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    return value.strip()


def _infer_domain_from_standard_name(standard_name: str, description: str = "") -> str:
    reference_text = f"{standard_name} {description}".upper()
    domain_rules = [
        ("Hydrology", ["SURFACE WATER", "GROUNDWATER", "RIVER", "DISCHARGE", "RUNOFF", "STREAM", "AQUIFER"]),
        ("Atmospheric Science", ["ATMOSPHERE", "AIR", "HUMIDITY", "PRECIPITATION", "RAINFALL", "TEMPERATURE", "WIND"]),
        ("Soil Science", ["SOIL", "STOMATAL", "HYDRAULIC CONDUCTIVITY", "POROSITY", "FIELD CAPACITY"]),
        ("Agriculture", ["CROP", "BIOMASS", "GRAIN", "FORAGE", "PLANT", "HARVEST", "RESIDUE"]),
        ("Oceanography", ["SEA", "OCEAN", "TIDE", "SALINITY", "ESTUARY", "COASTAL"]),
        ("Ecology", ["VEGETATION", "CANOPY", "ROOT", "LEAF", "ECOSYSTEM"]),
        ("Land Systems", ["LAND", "AREA", "USE", "ALLOCATION"]),
    ]
    for domain, markers in domain_rules:
        if any(marker in reference_text for marker in markers):
            return domain
    return "General Science"


def _keyword_candidates(*values: str) -> list[str]:
    keywords = []
    seen = set()
    for value in values:
        if not value:
            continue
        for candidate in re.split(r"[,;/]|(?:\s+-\s+)", value):
            cleaned = " ".join(candidate.lower().replace("_", " ").split())
            if len(cleaned) < 3:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                keywords.append(cleaned)
            for token in cleaned.split():
                if len(token) >= 4 and token not in seen:
                    seen.add(token)
                    keywords.append(token)
    return keywords[:12]


def _normalize_mint_variable(record: dict[str, Any]) -> tuple[str, dict[str, object]]:
    long_name = _first_nonempty(record, "hasLongName", "long_name", "longName")
    short_name = _first_nonempty(record, "hasShortName", "short_name", "shortName")
    display_name = _first_nonempty(
        record,
        "hasLongName",
        "long_name",
        "longName",
        "label",
        "name",
        "variable_name",
        "variableName",
        "standard_variable",
        "standardVariable",
    )
    standard_name = _first_nonempty(
        record,
        "hasStandardVariable",
        "standard_name",
        "standardName",
        "standard_variable",
        "standardVariable",
        "ontology_name",
        "ontologyName",
    ) or display_name
    units = _first_nonempty(record, "usesUnit", "units", "unit", "unit_names", "unitNames") or "unknown"
    description = _first_nonempty(record, "description", "definition", "summary")
    domain = _first_nonempty(record, "domain", "category", "theme", "realm")
    aliases = (
        _coerce_string_list(record.get("aliases"))
        + _coerce_string_list(record.get("synonyms"))
        + _coerce_string_list(record.get("hasShortName"))
        + _coerce_string_list(record.get("label"))
    )
    key_name = _slugify(display_name or standard_name or _first_nonempty(record, "id", "@id") or "mint_variable")
    human_label = _humanize_identifier(display_name or standard_name or key_name)
    human_standard_name = _humanize_identifier(standard_name)
    inferred_domain = _infer_domain_from_standard_name(human_standard_name, description)
    keywords = _keyword_candidates(human_label, short_name, human_standard_name, description, *aliases)
    return key_name, {
        "standard_name": human_standard_name,
        "units": _humanize_identifier(units),
        "data_source": "MINT variablepresentations API",
        "keywords": keywords or [key_name.replace("_", " ")],
        "domain": domain or inferred_domain,
        "label": human_label,
        "description": description,
        "short_name": short_name,
        "mint_id": _first_nonempty(record, "id", "@id"),
    }


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data", "variablepresentations", "variablePresentations"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def fetch_mint_svo_vocabulary(
    base_url: str,
    username: str = "mint@isi.edu",
    per_page: int = 200,
    max_pages: int = 3,
    timeout: int = 30,
) -> dict[str, dict[str, object]]:
    endpoint = f"{base_url.rstrip('/')}/variablepresentations"
    vocabulary = {}
    session = requests.Session()

    for page in range(1, max_pages + 1):
        response = session.get(
            endpoint,
            params={"username": username, "page": page, "per_page": per_page},
            timeout=timeout,
        )
        response.raise_for_status()
        records = _extract_records(response.json())
        if not records:
            break
        for record in records:
            key, normalized = _normalize_mint_variable(record)
            if key not in vocabulary:
                vocabulary[key] = normalized
        if len(records) < per_page:
            break

    if not vocabulary:
        raise RuntimeError("MINT variablepresentations returned no usable records")
    return vocabulary


def _extract_model_candidates(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data", "models", "modelconfigurations", "modelConfigurations"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_mint_model_candidate(record: dict[str, Any], candidate_kind: str) -> dict[str, Any]:
    model_reference = _first_nonempty(record, "hasModel", "model")
    model_name = _first_nonempty(record, "hasModelName", "model_name", "modelName", "title")
    if not model_name and model_reference:
        model_name = _identifier_tail(model_reference)

    configuration_label = _first_nonempty(record, "label", "name")
    fallback_id = _identifier_tail(_first_nonempty(record, "id", "@id"))
    label = model_name or configuration_label or fallback_id

    # Favor model names over configuration or variable labels for user-facing recommendations.
    if candidate_kind == "Model Configuration" and model_name:
        label = model_name

    description = _first_nonempty(record, "description", "shortDescription", "hasPurpose")
    keywords = _coerce_string_list(record.get("keywords"))
    categories = _coerce_string_list(record.get("hasModelCategory"))
    inputs = _coerce_string_list(record.get("hasInput"))
    outputs = _coerce_string_list(record.get("hasOutput"))
    processes = _coerce_string_list(record.get("hasProcess"))
    text_parts = [label, model_name, configuration_label, description, *keywords, *categories, *inputs, *outputs, *processes]
    searchable_text = " ".join(_humanize_identifier(part) for part in text_parts if part).lower()
    return {
        "id": _first_nonempty(record, "id", "@id"),
        "label": _humanize_identifier(label),
        "model_name": _humanize_identifier(model_name) if model_name else "",
        "configuration_label": _humanize_identifier(configuration_label) if configuration_label else "",
        "description": description,
        "keywords": keywords,
        "categories": categories,
        "inputs": inputs,
        "outputs": outputs,
        "processes": processes,
        "candidate_kind": candidate_kind,
        "searchable_text": searchable_text,
    }


def fetch_mint_model_candidates(
    base_url: str,
    username: str = "mint@isi.edu",
    per_page: int = 100,
    max_pages: int = 3,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    session = requests.Session()
    endpoints = [("models", "Model"), ("modelconfigurations", "Model Configuration")]
    candidates = []
    seen_ids = set()

    for endpoint_name, candidate_kind in endpoints:
        endpoint = f"{base_url.rstrip('/')}/{endpoint_name}"
        for page in range(1, max_pages + 1):
            response = session.get(
                endpoint,
                params={"username": username, "page": page, "per_page": per_page},
                timeout=timeout,
            )
            response.raise_for_status()
            records = _extract_model_candidates(response.json())
            if not records:
                break
            for record in records:
                normalized = _normalize_mint_model_candidate(record, candidate_kind)
                record_id = normalized["id"] or normalized["label"]
                if record_id in seen_ids:
                    continue
                seen_ids.add(record_id)
                candidates.append(normalized)
            if len(records) < per_page:
                break

    if not candidates:
        raise RuntimeError("MINT model catalog returned no usable model candidates")
    return candidates


def recommend_models_for_svo_mappings(
    unique_mappings: list[dict[str, str]],
    model_candidates: list[dict[str, Any]],
    recommendations_per_svo: int = 2,
    scientific_variables: list[str] | set[str] | None = None,
) -> list[dict[str, str]]:
    selected_variables = {value.strip() for value in (scientific_variables or []) if str(value).strip()}
    grouped = {}
    for mapping in unique_mappings:
        if selected_variables and mapping["scientific_variable"] not in selected_variables:
            continue
        grouped.setdefault(mapping["scientific_variable"], mapping)

    recommendations = []
    for scientific_variable, mapping in grouped.items():
        query_terms = {
            mapping["scientific_variable"].replace("_", " ").lower(),
            mapping["standard_name"].lower(),
            mapping["domain"].lower(),
            mapping["natural_language_term"].lower(),
        }
        query_terms.update(term for term in mapping["standard_name"].lower().split() if len(term) >= 4)
        scored = []
        for candidate in model_candidates:
            score = 0
            searchable_text = candidate["searchable_text"]
            for term in query_terms:
                if term and term in searchable_text:
                    score += 3 if " " in term else 1
            if mapping["domain"].lower() in " ".join(candidate["categories"]).lower():
                score += 3
            if mapping["natural_language_term"].lower() in searchable_text:
                score += 2
            if score > 0:
                scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], item[1]["label"]))
        for rank, (score, candidate) in enumerate(scored[:recommendations_per_svo], start=1):
            recommendations.append(
                {
                    "scientific_variable": scientific_variable,
                    "standard_name": mapping["standard_name"],
                    "domain": mapping["domain"],
                    "recommended_model": candidate.get("model_name") or candidate["label"],
                    "model_type": candidate["candidate_kind"],
                    "model_categories": ", ".join(candidate["categories"]),
                    "model_keywords": ", ".join(candidate["keywords"]),
                    "reason_score": score,
                    "model_description": candidate["description"],
                    "rank": rank,
                }
            )
    return recommendations


def recommend_mint_queries_for_topics(
    topics_info: dict[str, dict[str, Any]],
    model_candidates: list[dict[str, Any]],
    domains_per_topic: int = 3,
    tags_per_topic: int = 5,
) -> list[dict[str, Any]]:
    recommendations = []
    for topic_id, topic_info in topics_info.items():
        query_terms = set(topic_info["keywords"])
        query_terms.update(term for term in topic_display_name(topic_info).lower().replace(":", " ").split() if len(term) >= 4)
        query_terms.update(term for term in topic_info.get("description", "").lower().split() if len(term) >= 4)

        scored = []
        for candidate in model_candidates:
            score = 0
            searchable_text = candidate["searchable_text"]
            for term in query_terms:
                if term and term in searchable_text:
                    score += 3 if " " in term else 1
            if topic_info.get("description"):
                score += sum(1 for word in topic_info["description"].lower().split() if len(word) >= 6 and word in searchable_text)
            if score > 0:
                scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], item[1]["label"]))
        top_scored = scored[: max(domains_per_topic * 3, 6)]

        category_counts = Counter()
        keyword_counts = Counter()
        for score, candidate in top_scored:
            for category in candidate["categories"]:
                category_counts[_humanize_identifier(category)] += score
            for keyword in candidate["keywords"]:
                keyword_counts[_humanize_identifier(keyword)] += score

        recommendations.append(
            {
                "topic": topic_id,
                "label": topic_display_name(topic_info),
                "description": topic_info.get("description", ""),
                "query_domains": [name for name, _ in category_counts.most_common(domains_per_topic)],
                "query_tags": [name for name, _ in keyword_counts.most_common(tags_per_topic)],
            }
        )
    return recommendations
