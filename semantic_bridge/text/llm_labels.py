"""LLM-assisted topic labeling helpers."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from semantic_bridge.text.topics import topic_display_name

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    OpenAI = None


def _topic_context(
    topic_id: str,
    topic_info: dict[str, Any],
    doc_topic_dist,
    doc_names: list[str],
    documents: dict[str, str],
    top_document_count: int = 3,
    snippet_chars: int = 350,
) -> dict[str, Any]:
    topic_index = int(topic_id.split()[1]) - 1
    ranked_indices = doc_topic_dist[:, topic_index].argsort()[::-1][:top_document_count]
    top_documents = []
    for idx in ranked_indices:
        doc_name = doc_names[idx]
        snippet = documents[doc_name][:snippet_chars].replace("\n", " ").strip()
        top_documents.append(
            {
                "document": Path(doc_name).stem,
                "coverage": float(doc_topic_dist[idx, topic_index]),
                "snippet": snippet,
            }
        )
    return {
        "topic": topic_id,
        "keywords": topic_info["keywords"],
        "top_documents": top_documents,
    }


def _parse_json_response(content: str) -> dict[str, str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)

    candidates = [cleaned]
    object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate, strict=False)
            return {
                "label": str(payload.get("label", "")).strip(),
                "description": str(payload.get("description", "")).strip(),
            }
        except json.JSONDecodeError:
            continue

    label_match = re.search(r'"label"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    description_match = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    if label_match or description_match:
        return {
            "label": bytes((label_match.group(1) if label_match else ""), "utf-8").decode("unicode_escape").strip(),
            "description": bytes(
                (description_match.group(1) if description_match else ""),
                "utf-8",
            ).decode("unicode_escape").strip(),
        }

    one_line = " ".join(cleaned.split())
    return {
        "label": "",
        "description": one_line,
    }


def relabel_topics_with_llm(
    topics_info: dict[str, dict[str, Any]],
    doc_topic_dist,
    doc_names: list[str],
    documents: dict[str, str],
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    if OpenAI is None:
        raise RuntimeError("openai is not installed in this environment")
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    updated_topics = deepcopy(topics_info)

    for topic_id, topic_info in updated_topics.items():
        context = _topic_context(topic_id, topic_info, doc_topic_dist, doc_names, documents)
        prompt = (
            "You are helping label topic-model outputs for a tutorial notebook.\n"
            "Given topic keywords and short excerpts from high-coverage documents, "
            "write a concise, human-readable topic label and a one-sentence description.\n"
            "Return JSON with keys 'label' and 'description'.\n"
            "Keep the label under 6 words. Avoid repeating the raw keyword list."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(context, indent=2)},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_json_response(content)
        updated_topics[topic_id]["human_label"] = (
            f"{topic_id}: {parsed['label']}" if parsed["label"] else topic_display_name(topic_info)
        )
        updated_topics[topic_id]["description"] = parsed["description"]

    return updated_topics


def _parse_component_readability_response(content: str) -> dict[str, str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)

    candidates = [cleaned]
    object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate, strict=False)
            return {
                "readable_text": str(payload.get("readable_text", "")).strip(),
                "rationale": str(payload.get("rationale", "")).strip(),
            }
        except json.JSONDecodeError:
            continue

    one_line = " ".join(cleaned.split())
    return {"readable_text": one_line, "rationale": ""}


def improve_decision_component_readability_with_llm(
    components_df,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.1,
):
    """Rewrite extracted decision-component phrases into cleaner readable text.

    Returns a copy of ``components_df`` with two additional columns:
    ``readable_text`` and ``readable_rationale``.
    """

    if OpenAI is None:
        raise RuntimeError("openai is not installed in this environment")

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    updated_df = components_df.copy()
    readable_texts: list[str] = []
    readable_rationales: list[str] = []

    system_prompt = (
        "You are cleaning extracted decision-analysis phrases.\n"
        "Rewrite each extracted phrase into concise, human-readable text while preserving meaning.\n"
        "If the extracted phrase is person/place/noise and not a valid decision component, output a clearer component phrase using context.\n"
        "Return strict JSON with keys: readable_text, rationale.\n"
        "Keep readable_text under 10 words."
    )

    for row in updated_df.to_dict(orient="records"):
        payload = {
            "component_type": row.get("component_type", ""),
            "text": row.get("text", ""),
            "source": row.get("source", ""),
            "context": row.get("context", ""),
        }
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, indent=2)},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_component_readability_response(content)
        readable_text = parsed["readable_text"] or str(row.get("text", "")).strip()
        readable_texts.append(" ".join(readable_text.split()))
        readable_rationales.append(" ".join(parsed["rationale"].split()))

    updated_df["readable_text"] = readable_texts
    updated_df["readable_rationale"] = readable_rationales
    return updated_df
