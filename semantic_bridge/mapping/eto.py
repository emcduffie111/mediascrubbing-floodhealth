"""ETO Map of Science and science-backbone helpers.

This module intentionally absorbs the reusable parts of the ETO/SUBSIDE
notebooks: ETO CSV normalization, layer construction, layer merging, keyword
projection, and lightweight overlay analysis. The older helper functions remain
available as compatibility wrappers.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlencode

import pandas as pd

from semantic_bridge.text.topics import topic_display_name


ETO_MAP_BASE_URL = "https://sciencemap.eto.tech/"

ETO_CITATION = {
    "label": "ETO Map of Science",
    "url": "https://sciencemap.eto.tech/",
    "methodology_url": "https://eto.tech/dataset-docs/mac-clusters/",
}

UCSD_CITATION = {
    "label": "UCSD Map of Science",
    "citation": (
        "Borner K, Klavans R, Patek M, Zoss AM, Biberstine JR, Light RP, "
        "Lariviere V, Boyack KW (2012). Design and Update of a Classification "
        "System: The UCSD Map of Science. PLOS ONE 7(7): e39464."
    ),
    "doi": "https://doi.org/10.1371/journal.pone.0039464",
}

ETO_FIELD_TO_UCSD = {
    "earth science": "Earth Sciences",
    "biology": "Biology",
    "chemistry": "Chemistry",
    "materials science": "Chemistry",
    "computer science": "Electrical Engineering & Computer Science",
    "engineering": "Chemical, Mechanical, & Civil Engineering",
    "mathematics": "Math & Physics",
    "physics": "Math & Physics",
    "medicine": "Medical Specialties",
    "humanities": "Humanities",
    "social science": "Social Sciences",
    "business": "Social Sciences",
}

COMPACT_UCSD_SCAFFOLD = {
    "Math & Physics": {
        "subdisciplines": ["Mathematics", "Applied Mathematics", "Statistics", "Physics", "Astronomy"],
        "terms": ["mathematics", "statistics", "physics", "modeling", "simulation", "dynamics"],
    },
    "Chemistry": {
        "subdisciplines": ["Analytical Chemistry", "Organic Chemistry", "Materials Science"],
        "terms": ["chemistry", "chemical", "materials", "reaction", "compound", "polymer"],
    },
    "Earth Sciences": {
        "subdisciplines": ["Hydrology", "Hydrogeology", "Geomorphology", "Geophysics", "Geology"],
        "terms": ["earth", "geology", "hydrology", "groundwater", "geophysics", "climate", "sediment"],
    },
    "Biology": {
        "subdisciplines": ["Ecology", "Botany", "Zoology", "Evolutionary Biology"],
        "terms": ["biology", "ecology", "species", "ecosystem", "organism", "habitat"],
    },
    "Biotechnology": {
        "subdisciplines": ["Genetics", "Genomics", "Molecular Biology", "Bioengineering"],
        "terms": ["genetics", "genomics", "molecular", "biotechnology", "protein", "cell"],
    },
    "Infectious Diseases": {
        "subdisciplines": ["Virology", "Immunology", "Parasitology", "Epidemiology"],
        "terms": ["virus", "infection", "disease", "immune", "epidemiology", "pathogen"],
    },
    "Medical Specialties": {
        "subdisciplines": ["Cardiology", "Oncology", "Neurology", "Surgery"],
        "terms": ["clinical", "patient", "medicine", "therapy", "diagnosis", "health"],
    },
    "Health Professionals": {
        "subdisciplines": ["Public Health", "Nursing", "Health Services Research"],
        "terms": ["public health", "nursing", "health services", "care", "community health"],
    },
    "Brain Research": {
        "subdisciplines": ["Neuroscience", "Cognitive Science", "Psychiatry", "Psychology"],
        "terms": ["brain", "neuroscience", "cognition", "behavior", "mental health"],
    },
    "Electrical Engineering & Computer Science": {
        "subdisciplines": ["Computer Science", "Machine Learning", "Signal Processing", "Electrical Engineering"],
        "terms": ["computer", "algorithm", "machine learning", "signal", "software", "data"],
    },
    "Chemical, Mechanical, & Civil Engineering": {
        "subdisciplines": ["Civil Engineering", "Mechanical Engineering", "Chemical Engineering", "Geotechnical Engineering"],
        "terms": ["engineering", "infrastructure", "mechanical", "civil", "geotechnical", "materials"],
    },
    "Social Sciences": {
        "subdisciplines": ["Economics", "Political Science", "Sociology", "Geography", "Decision Science"],
        "terms": ["policy", "economics", "governance", "society", "decision", "stakeholder"],
    },
    "Humanities": {
        "subdisciplines": ["History", "Philosophy", "Literature", "Linguistics"],
        "terms": ["history", "philosophy", "literature", "language", "culture", "humanities"],
    },
}

DEFAULT_LABEL_STOPWORDS = {
    "about",
    "after",
    "analysis",
    "application",
    "applications",
    "based",
    "between",
    "from",
    "general",
    "into",
    "other",
    "research",
    "science",
    "sciences",
    "studies",
    "study",
    "that",
    "their",
    "these",
    "this",
    "using",
    "with",
}

_COLUMN_CANDIDATES = {
    "cluster_id": ["cluster id", "cluster_id", "clusterid", "id", "cluster"],
    "title": ["cluster title", "cluster_title", "cluster name", "cluster_name", "title", "name", "label"],
    "summary": ["cluster summary", "cluster_summary", "summary", "description", "abstract"],
    "discipline": [
        "top discipline",
        "primary discipline",
        "research discipline",
        "discipline",
        "disciplines",
        "research disciplines",
    ],
    "field": [
        "most common research field",
        "most common field",
        "research field",
        "top field",
        "field",
        "fields",
    ],
    "subfield": ["top subfield", "subfield", "subfields"],
    "topic": ["top topic", "topic", "topics"],
    "key_concepts": ["key concepts", "concepts", "keywords", "key subjects", "subjects"],
    "size": ["cluster size", "cluster_size", "size", "n articles", "narticles", "article count", "articlecount"],
    "growth": ["growth rating", "growth_rating", "growth"],
    "citation": ["citation rating", "citation_rating", "citation"],
}


def _normalize_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split()).strip()


def _humanize_label(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:]


def _unique_preserve_order(values: Iterable[Any]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        normalized = _clean_text(value)
        if not normalized:
            continue
        marker = normalized.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(normalized)
    return ordered


def _pick_existing_columns(columns: list[str], candidates: list[str]) -> list[str]:
    normalized_lookup = {_normalize_column_name(column): column for column in columns}
    matched = []
    for candidate in candidates:
        column = normalized_lookup.get(_normalize_column_name(candidate))
        if column and column not in matched:
            matched.append(column)
    return matched


def _find_first_column(columns: list[str], candidates: list[str]) -> str | None:
    matches = _pick_existing_columns(columns, candidates)
    return matches[0] if matches else None


def _split_multivalue_cell(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        return _unique_preserve_order(part for item in value for part in _split_multivalue_cell(item))

    text = _clean_text(value)
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return _split_multivalue_cell(decoded)

    parts = re.split(r"\s*[|;,]\s*|\s{2,}", text)
    return _unique_preserve_order(parts)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _term_tokens(*values: Any, stopwords: set[str] | None = None) -> list[str]:
    stop = stopwords or DEFAULT_LABEL_STOPWORDS
    terms = []
    for value in values:
        for token in re.findall(r"[a-z][a-z0-9-]+", _clean_text(value).lower()):
            if len(token) > 2 and token not in stop:
                terms.append(token)
    return _unique_preserve_order(terms)


def _node_subdisciplines(node: Any) -> list[str]:
    if isinstance(node, dict):
        return list(node.get("subdisciplines") or node.get("subs") or ["General"])
    if isinstance(node, list):
        return list(node)
    return ["General"]


def _node_terms(node: Any, domain: str) -> list[str]:
    if isinstance(node, dict):
        terms = node.get("terms") or node.get("keywords") or []
    else:
        terms = []
    return _unique_preserve_order([domain, *_node_subdisciplines(node), *terms])


def _normalize_backbone(backbone: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    normalized = {}
    for domain, node in (backbone or {}).items():
        if isinstance(node, dict):
            normalized[domain] = {
                "subdisciplines": _unique_preserve_order(node.get("subdisciplines") or node.get("subs") or ["General"]),
                "terms": _unique_preserve_order(node.get("terms") or node.get("keywords") or []),
                **{key: deepcopy(value) for key, value in node.items() if key not in {"subdisciplines", "subs", "terms", "keywords"}},
            }
        else:
            normalized[domain] = {
                "subdisciplines": _unique_preserve_order(node if isinstance(node, list) else ["General"]),
                "terms": [],
            }
    return normalized


def _domain_key(label: str) -> str:
    tokens = []
    for token in re.findall(r"[a-z0-9]+", label.lower()):
        if token.endswith("ies"):
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 3:
            token = token[:-1]
        tokens.append(token)
    return " ".join(tokens)


def _domain_match_score(left: str, right: str) -> float:
    left_key = _domain_key(left)
    right_key = _domain_key(right)
    if left_key == right_key:
        return 1.0
    left_tokens = set(left_key.split())
    right_tokens = set(right_key.split())
    if not left_tokens or not right_tokens:
        return 0.0
    if left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens):
        return 0.85
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def resolve_eto_columns(columns: Iterable[str]) -> dict[str, str]:
    """Resolve known ETO export column variants to canonical names."""

    source_columns = list(columns)
    resolved = {}
    for canonical, candidates in _COLUMN_CANDIDATES.items():
        column = _find_first_column(source_columns, candidates)
        if column:
            resolved[canonical] = column
    return resolved


def build_eto_map_url(
    subjects: list[str] | None = None,
    mode: str = "list",
    extra_params: dict[str, Any] | None = None,
) -> str:
    params: dict[str, Any] = {"mode": mode}
    if subjects:
        params["all_subjects"] = ", ".join(_unique_preserve_order(subjects))
    if extra_params:
        params.update({key: value for key, value in extra_params.items() if value not in (None, "")})
    return f"{ETO_MAP_BASE_URL}?{urlencode(params, doseq=True)}"


def recommend_eto_queries_for_topics(
    topics_info: dict[str, dict[str, Any]],
    keywords_per_topic: int = 3,
) -> list[dict[str, Any]]:
    recommendations = []
    for topic_id, topic_info in topics_info.items():
        subject_terms = _unique_preserve_order(topic_info.get("keywords", [])[:keywords_per_topic])
        recommendations.append(
            {
                "topic": topic_id,
                "label": topic_display_name(topic_info),
                "description": topic_info.get("description", ""),
                "subjects": subject_terms,
                "eto_list_url": build_eto_map_url(subject_terms, mode="list"),
                "eto_map_url": build_eto_map_url(subject_terms, mode="map"),
            }
        )
    return recommendations


def prepare_eto_query_exports(
    output_dir: Path,
    topics_info: dict[str, dict[str, Any]],
    keywords_per_topic: int = 3,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    eto_export_path = output_dir / "eto_map_export.csv"
    eto_query_export_path = output_dir / "eto_query_recommendations.csv"
    eto_topic_queries = recommend_eto_queries_for_topics(
        topics_info,
        keywords_per_topic=keywords_per_topic,
    )
    pd.DataFrame(eto_topic_queries).to_csv(eto_query_export_path, index=False)
    return {
        "eto_export_path": eto_export_path,
        "eto_query_export_path": eto_query_export_path,
        "eto_topic_queries": eto_topic_queries,
    }


def load_eto_cluster_export(csv_path: Path) -> pd.DataFrame:
    cluster_df = pd.read_csv(csv_path)
    cluster_df.columns = [str(column).strip() for column in cluster_df.columns]
    return cluster_df


def normalize_eto_cluster_records(
    cluster_data: pd.DataFrame | Iterable[dict[str, Any]],
    title_filter: Iterable[str] | str | None = None,
    field_whitelist: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Normalize ETO CSV exports across old and current column layouts."""

    if isinstance(cluster_data, pd.DataFrame):
        columns = resolve_eto_columns(cluster_data.columns)
        records = []
        for raw_index, row in cluster_data.iterrows():
            record = {"raw_row_index": int(raw_index)}
            for canonical, actual in columns.items():
                value = row.get(actual)
                record[canonical] = None if value is None or (isinstance(value, float) and pd.isna(value)) else value
            records.append(record)
    else:
        records = []
        for raw_index, item in enumerate(cluster_data):
            record = {str(key): value for key, value in item.items()}
            record.setdefault("raw_row_index", raw_index)
            records.append(record)

    normalized = []
    for record in records:
        clean_record = dict(record)
        for key in ("discipline", "field", "subfield", "topic", "key_concepts"):
            clean_record[f"{key}_values"] = _split_multivalue_cell(clean_record.get(key))
        clean_record["title"] = _clean_text(clean_record.get("title"))
        clean_record["summary"] = _clean_text(clean_record.get("summary"))
        clean_record["cluster_id"] = _clean_text(clean_record.get("cluster_id"))
        clean_record["size_value"] = _coerce_float(clean_record.get("size"))
        searchable = [
            clean_record.get("title", ""),
            clean_record.get("summary", ""),
            *clean_record.get("discipline_values", []),
            *clean_record.get("field_values", []),
            *clean_record.get("subfield_values", []),
            *clean_record.get("topic_values", []),
            *clean_record.get("key_concepts_values", []),
        ]
        clean_record["searchable_text"] = " ".join(_clean_text(value) for value in searchable).lower()
        normalized.append(clean_record)

    if title_filter:
        filters = [title_filter] if isinstance(title_filter, str) else list(title_filter)
        filters_l = [str(item).lower() for item in filters if str(item).strip()]
        normalized = [
            record
            for record in normalized
            if any(term in record["searchable_text"] for term in filters_l)
        ]

    if field_whitelist:
        whitelist = {str(field).lower().strip() for field in field_whitelist}
        normalized = [
            record
            for record in normalized
            if any(str(field).lower().strip() in whitelist for field in record.get("field_values", []))
        ]

    return normalized


def _domain_for_record(
    record: dict[str, Any],
    prefer_ucsd_fields: bool = False,
    field_to_domain: dict[str, str] | None = None,
) -> str:
    disciplines = record.get("discipline_values") or _split_multivalue_cell(record.get("discipline"))
    fields = record.get("field_values") or _split_multivalue_cell(record.get("field"))

    if disciplines:
        return disciplines[0]
    if fields:
        field = fields[0]
        if prefer_ucsd_fields:
            lookup = field_to_domain or ETO_FIELD_TO_UCSD
            return lookup.get(field.lower(), f"ETO:{_humanize_label(field)}")
        return _humanize_label(field)
    return "General"


def _subdiscipline_candidates(record: dict[str, Any], domain: str) -> list[str]:
    values = []
    for key in ("field_values", "subfield_values", "topic_values"):
        values.extend(record.get(key) or [])
    values = [value for value in values if _domain_match_score(value, domain) < 0.85]
    if not values and record.get("title"):
        values.append(record["title"])
    return _unique_preserve_order(values or ["General"])


def build_eto_science_backbone(
    cluster_data: pd.DataFrame | Iterable[dict[str, Any]],
    *,
    title_filter: Iterable[str] | str | None = None,
    field_whitelist: Iterable[str] | None = None,
    prefer_ucsd_fields: bool = False,
    field_to_domain: dict[str, str] | None = None,
    max_subdisciplines_per_domain: int = 25,
    max_terms_per_domain: int = 80,
    include_clusters: bool = True,
) -> dict[str, dict[str, Any]]:
    """Build a rich science backbone from an ETO cluster export."""

    records = normalize_eto_cluster_records(
        cluster_data,
        title_filter=title_filter,
        field_whitelist=field_whitelist,
    )
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_domain[_domain_for_record(record, prefer_ucsd_fields, field_to_domain)].append(record)

    backbone = {}
    for domain, members in by_domain.items():
        subdisciplines = []
        terms = []
        cluster_summaries = []
        members_sorted = sorted(members, key=lambda item: -item.get("size_value", 0.0))
        for record in members_sorted:
            for subdiscipline in _subdiscipline_candidates(record, domain):
                if len(subdisciplines) < max_subdisciplines_per_domain:
                    subdisciplines.append(subdiscipline)
            terms.extend(_subdiscipline_candidates(record, domain))
            terms.extend(record.get("key_concepts_values") or [])
            terms.extend(_term_tokens(record.get("title"), record.get("summary")))
            if include_clusters:
                cluster_summaries.append(
                    {
                        "cluster_id": record.get("cluster_id", ""),
                        "title": record.get("title", ""),
                        "field": ", ".join(record.get("field_values") or []),
                        "size": record.get("size_value", 0.0),
                    }
                )

        node = {
            "subdisciplines": _unique_preserve_order(subdisciplines) or ["General"],
            "terms": _unique_preserve_order(terms)[:max_terms_per_domain] or [domain.lower()],
            "source": "ETO Map of Science cluster CSV export",
            "metadata": {
                "n_clusters": len(members),
                "prefer_ucsd_fields": prefer_ucsd_fields,
                "fields": dict(Counter(field for member in members for field in member.get("field_values", []))),
            },
        }
        if include_clusters:
            node["clusters"] = cluster_summaries
        backbone[domain] = node
    return backbone


def build_science_backbone_from_eto_export(
    cluster_df: pd.DataFrame,
    *,
    rich: bool = False,
    title_filter: Iterable[str] | str | None = None,
    field_whitelist: Iterable[str] | None = None,
    prefer_ucsd_fields: bool = False,
) -> dict[str, list[str]] | dict[str, dict[str, Any]]:
    """Build a science backbone from ETO CSV data.

    By default this preserves the original lightweight return shape:
    ``{domain: [subdiscipline, ...]}``. Pass ``rich=True`` to get nodes with
    terms, source metadata, and cluster summaries.
    """

    if rich:
        return build_eto_science_backbone(
            cluster_df,
            title_filter=title_filter,
            field_whitelist=field_whitelist,
            prefer_ucsd_fields=prefer_ucsd_fields,
        )

    records = normalize_eto_cluster_records(
        cluster_df,
        title_filter=title_filter,
        field_whitelist=field_whitelist,
    )
    backbone: dict[str, list[str]] = {}
    for record in records:
        domain = _domain_for_record(record, prefer_ucsd_fields=prefer_ucsd_fields)
        domain_subs = backbone.setdefault(domain, [])
        for subdiscipline in _subdiscipline_candidates(record, domain):
            if subdiscipline not in domain_subs:
                domain_subs.append(subdiscipline)
    return backbone


def materialize_ucsd_scaffold(
    scaffold: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return a rich UCSD-style reference layer."""

    source = scaffold or COMPACT_UCSD_SCAFFOLD
    backbone = {}
    for domain, node in source.items():
        backbone[domain] = {
            "subdisciplines": _unique_preserve_order(node.get("subdisciplines") or ["General"]),
            "terms": _unique_preserve_order(node.get("terms") or []),
            "source": node.get("source", "UCSD Map of Science compact scaffold"),
            "metadata": deepcopy(node.get("metadata", {})),
        }
    return backbone


def merge_science_backbone_layers(
    eto_layer: dict[str, Any] | None,
    base_layer: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Merge an ETO layer into a base layer such as UCSD."""

    eto = _normalize_backbone(eto_layer)
    base = _normalize_backbone(base_layer)
    if not base:
        return eto
    if not eto:
        return base

    merged = deepcopy(base)
    for eto_domain, eto_node in eto.items():
        candidates = [(base_domain, _domain_match_score(eto_domain, base_domain)) for base_domain in merged]
        match, score = max(candidates, key=lambda item: item[1])
        if score >= 0.5:
            merged[match]["subdisciplines"] = _unique_preserve_order(
                [*merged[match].get("subdisciplines", []), *eto_node.get("subdisciplines", [])]
            )
            merged[match]["terms"] = _unique_preserve_order(
                [*merged[match].get("terms", []), *eto_node.get("terms", [])]
            )
            merged[match]["source"] = "Base science backbone extended by ETO Map of Science"
            metadata = dict(merged[match].get("metadata", {}))
            metadata["eto_match"] = eto_domain
            metadata["eto_n_clusters"] = eto_node.get("metadata", {}).get("n_clusters")
            merged[match]["metadata"] = metadata
            if eto_node.get("clusters"):
                merged[match]["clusters"] = eto_node["clusters"]
        else:
            merged[eto_domain] = {
                **deepcopy(eto_node),
                "source": f"ETO only; no base-layer match above threshold ({score:.2f})",
            }
    return merged


def build_science_backbone_payload(
    *,
    eto_csv_path: Path | str | None = None,
    eto_cluster_df: pd.DataFrame | None = None,
    base_layer: dict[str, Any] | None = None,
    title_filter: Iterable[str] | str | None = None,
    field_whitelist: Iterable[str] | None = None,
    selected_layer: str = "merged",
    prefer_ucsd_fields: bool = True,
) -> dict[str, Any]:
    """Build a portable multi-layer science-backbone JSON payload."""

    eto_df = eto_cluster_df
    if eto_df is None and eto_csv_path:
        eto_df = load_eto_cluster_export(Path(eto_csv_path))

    layer_eto = (
        build_eto_science_backbone(
            eto_df,
            title_filter=title_filter,
            field_whitelist=field_whitelist,
            prefer_ucsd_fields=prefer_ucsd_fields,
        )
        if eto_df is not None
        else {}
    )
    layer_base = materialize_ucsd_scaffold(base_layer) if base_layer is not None else materialize_ucsd_scaffold()
    layer_merged = merge_science_backbone_layers(layer_eto, layer_base)
    layers = {"eto": layer_eto, "ucsd": layer_base, "merged": layer_merged}
    if selected_layer not in layers or not layers[selected_layer]:
        selected_layer = "merged" if layer_merged else "ucsd" if layer_base else "eto"

    return {
        "schema_version": "semantic-bridge-science-backbone-v1",
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "produced_by": "semantic_bridge.mapping.eto.build_science_backbone_payload",
        "selected_layer": selected_layer,
        "citations": {"eto": ETO_CITATION, "ucsd": UCSD_CITATION},
        "sources": {
            "eto_csv_path": str(eto_csv_path) if eto_csv_path else None,
            "title_filter": list(title_filter) if title_filter and not isinstance(title_filter, str) else title_filter,
            "field_whitelist": list(field_whitelist) if field_whitelist else None,
        },
        "layers": layers,
    }


def selected_science_backbone(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    layers = payload.get("layers", {})
    selected = payload.get("selected_layer") or "merged"
    return layers.get(selected) or layers.get("merged") or layers.get("ucsd") or layers.get("eto") or {}


def write_science_backbone_payload(payload: dict[str, Any], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_science_backbone_payload(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _topic_query_terms(topic_data: dict[str, Any]) -> set[str]:
    terms = {
        keyword.lower()
        for keyword in topic_data.get("keywords", [])
        if isinstance(keyword, str) and keyword.strip()
    }
    for token in topic_display_name(topic_data).lower().replace(":", " ").split():
        if len(token) >= 4:
            terms.add(token)
    return terms


def map_topics_to_eto_clusters(
    topics_info: dict[str, dict[str, Any]],
    cluster_df: pd.DataFrame,
    top_matches: int = 3,
) -> list[dict[str, Any]]:
    records = normalize_eto_cluster_records(cluster_df)
    if not records:
        return []

    mappings = []
    for topic_id, topic_data in topics_info.items():
        query_terms = _topic_query_terms(topic_data)
        candidates = []
        for record in records:
            score = 0
            searchable_text = record.get("searchable_text", "")
            for term in query_terms:
                if term in searchable_text:
                    score += 3 if " " in term else 1
            if score > 0:
                candidates.append((score, record))

        candidates.sort(key=lambda item: (-item[0], item[1].get("title", "")))
        best_matches = candidates[:top_matches]
        first_record = best_matches[0][1] if best_matches else {}
        primary_domain = _domain_for_record(first_record) if first_record else "General"
        secondary_values = [
            *first_record.get("field_values", []),
            *first_record.get("subfield_values", []),
            *first_record.get("topic_values", []),
        ]
        secondary_domain = next((value for value in secondary_values if value != primary_domain), None)

        mappings.append(
            {
                "topic": topic_id,
                "topic_label": topic_display_name(topic_data),
                "keywords": ", ".join(topic_data.get("keywords", [])[:5]),
                "primary_domain": primary_domain or "General",
                "secondary_domain": secondary_domain,
                "eto_matches": [
                    {
                        "cluster_id": match_record.get("cluster_id", ""),
                        "cluster_name": match_record.get("title", ""),
                        "score": score,
                    }
                    for score, match_record in best_matches
                ],
            }
        )
    return mappings


def _score_terms_against_backbone(query_terms: list[str], target_terms: list[str]) -> tuple[int, list[str]]:
    target_l = [term.lower() for term in target_terms]
    matched = []
    for query in query_terms:
        query_l = query.lower()
        if any(query_l == target or query_l in target or target in query_l for target in target_l):
            matched.append(query)
    return len(matched), _unique_preserve_order(matched)


def map_terms_to_science_backbone(
    terms: Iterable[str],
    backbone: dict[str, Any],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    query_terms = [str(term).lower() for term in terms if str(term).strip()]
    hits = []
    for domain, node in backbone.items():
        subs = _node_subdisciplines(node)
        node_terms = _node_terms(node, domain)
        for subdiscipline in subs:
            target_terms = _unique_preserve_order([domain, subdiscipline, *node_terms])
            score, matched_terms = _score_terms_against_backbone(query_terms, target_terms)
            if score > 0:
                hits.append(
                    {
                        "domain": domain,
                        "subdiscipline": subdiscipline,
                        "score": score,
                        "matched_terms": matched_terms,
                    }
                )
    if not hits:
        return [{"domain": "Uncategorized", "subdiscipline": "General", "score": 0, "matched_terms": []}]
    return sorted(hits, key=lambda item: (-item["score"], item["domain"], item["subdiscipline"]))[:top_n]


def map_keyword_groups_to_backbone(
    keyword_groups: dict[str, Iterable[str]],
    backbone: dict[str, Any],
    *,
    document_match_counts: dict[str, int] | None = None,
    top_n: int = 3,
    as_dataframe: bool = False,
) -> list[dict[str, Any]] | pd.DataFrame:
    rows = []
    for name, terms in keyword_groups.items():
        hits = map_terms_to_science_backbone(terms, backbone, top_n=top_n)
        rows.append(
            {
                "group": name,
                "primary_domain": hits[0]["domain"],
                "backbone_mapping": [
                    (hit["domain"], hit["subdiscipline"], hit["score"])
                    for hit in hits
                ],
                "matched_terms": {
                    f"{hit['domain']}::{hit['subdiscipline']}": hit["matched_terms"]
                    for hit in hits
                },
                "n_matches": int((document_match_counts or {}).get(name, 0)),
            }
        )
    return pd.DataFrame(rows) if as_dataframe else rows


def count_group_terms_in_text(text: str, group_terms: Iterable[str]) -> int:
    text_l = text.lower()
    total = 0
    for term in group_terms:
        term_l = str(term).lower().strip()
        if not term_l:
            continue
        if " " in term_l or "-" in term_l:
            total += text_l.count(term_l)
        else:
            total += len(re.findall(rf"\b{re.escape(term_l)}\b", text_l))
    return total


def project_documents_onto_backbone(
    documents: dict[str, str],
    keyword_groups: dict[str, Iterable[str]],
    group_mappings: list[dict[str, Any]] | pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Project document text onto a fixed backbone through keyword groups."""

    rows = []
    for doc_name, text in documents.items():
        n_words = len(str(text).split())
        for group, terms in keyword_groups.items():
            count = count_group_terms_in_text(str(text), terms)
            rows.append(
                {
                    "doc": doc_name,
                    "group": group,
                    "count": count,
                    "doc_n_words": n_words,
                    "per_1k_words": round(1000 * count / max(n_words, 1), 2),
                }
            )
    doc_group_df = pd.DataFrame(
        rows,
        columns=["doc", "group", "count", "doc_n_words", "per_1k_words"],
    )
    group_totals = (
        doc_group_df.groupby("group")["count"].sum().reset_index().sort_values("count", ascending=False)
        if len(doc_group_df)
        else pd.DataFrame(columns=["group", "count"])
    )

    if isinstance(group_mappings, pd.DataFrame):
        mapping_rows = group_mappings.to_dict("records")
    else:
        mapping_rows = group_mappings

    counts_by_group = group_totals.set_index("group")["count"].to_dict() if len(group_totals) else {}
    domain_weights: dict[str, float] = defaultdict(float)
    subdiscipline_weights: dict[tuple[str, str], float] = defaultdict(float)
    for row in mapping_rows:
        group = row["group"]
        group_count = float(counts_by_group.get(group, 0))
        mappings = row.get("backbone_mapping") or []
        if group_count <= 0 or not mappings:
            continue
        total_score = sum(float(score) for _, _, score in mappings) or 1.0
        for domain, subdiscipline, score in mappings:
            weight = group_count * (float(score) / total_score)
            domain_weights[domain] += weight
            subdiscipline_weights[(domain, subdiscipline)] += weight

    domain_totals = pd.DataFrame(
        [{"domain": domain, "weight": weight} for domain, weight in domain_weights.items()],
        columns=["domain", "weight"],
    ).sort_values("weight", ascending=False, ignore_index=True)
    subdiscipline_totals = pd.DataFrame(
        [
            {"domain": domain, "subdiscipline": subdiscipline, "weight": weight}
            for (domain, subdiscipline), weight in subdiscipline_weights.items()
        ],
        columns=["domain", "subdiscipline", "weight"],
    ).sort_values("weight", ascending=False, ignore_index=True)

    return {
        "doc_group_counts": doc_group_df,
        "group_totals": group_totals,
        "domain_totals": domain_totals,
        "subdiscipline_totals": subdiscipline_totals,
    }


__all__ = [
    "COMPACT_UCSD_SCAFFOLD",
    "ETO_CITATION",
    "ETO_FIELD_TO_UCSD",
    "ETO_MAP_BASE_URL",
    "UCSD_CITATION",
    "build_eto_map_url",
    "build_eto_science_backbone",
    "build_science_backbone_from_eto_export",
    "build_science_backbone_payload",
    "count_group_terms_in_text",
    "load_eto_cluster_export",
    "map_keyword_groups_to_backbone",
    "map_terms_to_science_backbone",
    "map_topics_to_eto_clusters",
    "materialize_ucsd_scaffold",
    "merge_science_backbone_layers",
    "normalize_eto_cluster_records",
    "prepare_eto_query_exports",
    "project_documents_onto_backbone",
    "read_science_backbone_payload",
    "recommend_eto_queries_for_topics",
    "resolve_eto_columns",
    "selected_science_backbone",
    "write_science_backbone_payload",
]
