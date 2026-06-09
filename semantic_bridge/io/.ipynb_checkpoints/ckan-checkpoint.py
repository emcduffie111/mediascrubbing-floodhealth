"""CKAN authentication, synchronization, and registration helpers."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
from pathlib import Path
import re
from typing import Any
from typing import Callable
from typing import Iterable

import requests

from semantic_bridge.io.documents import SUPPORTED_DOCUMENT_SUFFIXES, ensure_data_directory, load_pdf_document

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    OpenAI = None


DEFAULT_TAPIS_URL = "https://portals.tapis.io/v3/oauth2/tokens"
LOGGER = logging.getLogger(__name__)


def _ckan_debug_enabled() -> bool:
    value = os.getenv("CKAN_DEBUG", "").strip().lower()
    return value in {"1", "true", "yes", "on", "debug"}


def _mask_secret(value: str, keep: int = 12) -> str:
    text = str(value or "")
    if len(text) <= keep:
        return "***"
    return f"{text[:keep]}...<redacted>"


def _sanitize_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in {"authorization", "api_key", "apikey", "token", "password"}:
                sanitized[key] = _mask_secret(str(item))
            elif normalized in {"notes", "description"} and isinstance(item, str) and len(item) > 300:
                sanitized[key] = f"{item[:300]}...<truncated>"
            else:
                sanitized[key] = _sanitize_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_log(item) for item in value]
    if isinstance(value, str) and len(value) > 600:
        return f"{value[:600]}...<truncated>"
    return value


def get_tapis_token(username: str, password: str, *, tapis_url: str = DEFAULT_TAPIS_URL) -> str:
    response = requests.post(
        tapis_url,
        data={
            "username": username,
            "password": password,
            "grant_type": "password",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["result"]["access_token"]["access_token"]


def build_ckan_auth_header(
    *,
    auth_mode: str,
    api_token: str | None = None,
    username: str | None = None,
    password: str | None = None,
    tapis_url: str = DEFAULT_TAPIS_URL,
) -> str | None:
    normalized_mode = (auth_mode or "api_token").strip().lower()
    if normalized_mode == "api_token":
        token = (api_token or "").strip()
        return token or None
    if normalized_mode == "tapis_password":
        user = (username or "").strip()
        secret = password or ""
        if not user or not secret:
            raise ValueError("TACC username and password are required for CKAN tapis_password authentication.")
        return f"Bearer {get_tapis_token(user, secret, tapis_url=tapis_url)}"
    raise ValueError(f"Unsupported CKAN auth mode: {auth_mode}")


def auth_headers(auth_header: str | None = None) -> dict[str, str]:
    if not auth_header:
        return {}
    return {"Authorization": auth_header}


def fetch_ckan_dataset(
    base_url: str,
    dataset_name: str,
    auth_header: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    if _ckan_debug_enabled():
        LOGGER.debug(
            "CKAN request action=package_show url=%s params=%s",
            f"{base_url.rstrip('/')}/api/3/action/package_show",
            {"id": dataset_name},
        )
    response = requests.get(
        f"{base_url.rstrip('/')}/api/3/action/package_show",
        params={"id": dataset_name},
        headers=auth_headers(auth_header),
        timeout=timeout,
    )
    if _ckan_debug_enabled():
        debug_payload: Any
        try:
            debug_payload = response.json()
        except ValueError:
            debug_payload = response.text[:1200]
        LOGGER.debug(
            "CKAN response action=package_show status=%s body=%s",
            response.status_code,
            _sanitize_for_log(debug_payload),
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError(f"CKAN package_show failed for {dataset_name}")
    return payload["result"]


def _ckan_action_url(base_url: str, action: str) -> str:
    return f"{base_url.rstrip('/')}/api/3/action/{action}"


def _ckan_action_post(
    base_url: str,
    action: str,
    payload: dict[str, Any],
    auth_header: str | None = None,
    *,
    files: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    headers = auth_headers(auth_header)
    request_kwargs: dict[str, Any] = {
        "headers": headers,
        "timeout": timeout,
    }
    if files:
        request_kwargs["data"] = payload
        request_kwargs["files"] = files
    else:
        request_kwargs["json"] = payload

    if _ckan_debug_enabled():
        file_keys = list(files.keys()) if files else []
        LOGGER.debug(
            "CKAN request action=%s url=%s files=%s payload=%s",
            action,
            _ckan_action_url(base_url, action),
            file_keys,
            _sanitize_for_log(payload),
        )

    response = requests.post(_ckan_action_url(base_url, action), **request_kwargs)
    try:
        body = response.json()
    except ValueError:
        body = {}

    if _ckan_debug_enabled():
        LOGGER.debug(
            "CKAN response action=%s status=%s body=%s",
            action,
            response.status_code,
            _sanitize_for_log(body if body else response.text[:1200]),
        )

    if response.status_code >= 400:
        error_payload = body.get("error") if isinstance(body, dict) else None
        detail = error_payload if error_payload else response.text[:1000]
        raise ValueError(f"CKAN {action} HTTP {response.status_code}: {detail}")

    if not body.get("success"):
        raise ValueError(f"CKAN {action} failed: {body.get('error')}")
    return body["result"]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def collect_pdf_resources(corpus_dir: Path) -> list[Path]:
    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory does not exist: {corpus_dir}")
    return sorted(path for path in corpus_dir.rglob("*.pdf") if path.is_file())


def _sanitize_tag(tag: str) -> str:
    return slugify(tag)[:100]


def _normalize_tag_list(tags: Iterable[str]) -> list[dict[str, str]]:
    unique = []
    seen = set()
    for tag in tags:
        normalized = _sanitize_tag(tag)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append({"name": normalized})
    return unique


def _deduplicate_tags(tags: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen = set()
    for tag in tags:
        normalized = _sanitize_tag(_clean_text(tag, max_chars=48).lower())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _ensure_unique_resource_titles(resource_plan: list[dict[str, Any]]) -> None:
    title_counts: dict[str, int] = {}
    for resource in resource_plan:
        key = _clean_text(resource.get("resource_title"), max_chars=140).lower()
        if key:
            title_counts[key] = title_counts.get(key, 0) + 1

    for resource in resource_plan:
        title = _clean_text(resource.get("resource_title"), max_chars=140)
        key = title.lower()
        if title and title_counts.get(key, 0) > 1:
            stem = Path(str(resource.get("resource_name", ""))).stem
            resource["resource_title"] = f"{title} ({stem})"


def _parse_llm_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates = [cleaned]
    object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    return {}


def _clean_text(value: Any, max_chars: int | None = None) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def _pdf_preview_text(pdf_path: Path, max_chars: int = 5000) -> str:
    extracted = load_pdf_document(pdf_path)
    return _clean_text(extracted, max_chars=max_chars)


def extract_ckan_resource_metadata_with_llm(
    pdf_path: Path,
    *,
    model: str,
    api_key: str,
    base_url: str | None = None,
    max_chars: int = 5000,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Infer CKAN resource title, description, and tags from a PDF excerpt."""

    if OpenAI is None:
        raise RuntimeError("openai is not installed in this environment")

    excerpt = _pdf_preview_text(pdf_path, max_chars=max_chars)
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    prompt = (
        "You are generating CKAN metadata for one PDF resource.\n"
        "Return strict JSON with keys: resource_title, resource_description, resource_tags.\n"
        "resource_tags must be a list of short lowercase keyword strings."
    )
    payload = {
        "filename": pdf_path.name,
        "excerpt": excerpt,
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, indent=2)},
        ],
        temperature=temperature,
    )
    parsed = _parse_llm_json(response.choices[0].message.content or "")

    fallback_title = pdf_path.stem.replace("_", " ").replace("-", " ").strip() or pdf_path.name
    title = _clean_text(parsed.get("resource_title") or fallback_title, max_chars=140)
    description = _clean_text(
        parsed.get("resource_description") or f"Source document uploaded from {pdf_path.name}.",
        max_chars=3000,
    )
    raw_tags = parsed.get("resource_tags")
    tags = raw_tags if isinstance(raw_tags, list) else []
    cleaned_tags = _deduplicate_tags(tags)
    if not cleaned_tags:
        cleaned_tags = ["document", "pdf"]

    return {
        "resource_name": pdf_path.name,
        "resource_title": title,
        "resource_description": description,
        "resource_tags": cleaned_tags,
    }


def build_ckan_registration_plan_with_llm(
    pdf_paths: list[Path],
    *,
    model: str,
    api_key: str,
    base_url: str | None = None,
    dataset_name: str | None = None,
    dataset_title: str | None = None,
    max_chars_per_pdf: int = 5000,
    progress_callback: Callable[[int, int, Path], None] | None = None,
    result_callback: Callable[[int, int, Path, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Build CKAN dataset + resource metadata from a corpus of PDFs.

    This sends one LLM request per PDF (not one single request for all PDFs).
    """

    if not pdf_paths:
        raise ValueError("No PDF files were provided for CKAN registration.")

    resource_plan: list[dict[str, Any]] = []
    total = len(pdf_paths)
    for index, pdf_path in enumerate(pdf_paths, start=1):
        if progress_callback is not None:
            progress_callback(index, total, pdf_path)
        resource_metadata = extract_ckan_resource_metadata_with_llm(
            pdf_path,
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_chars=max_chars_per_pdf,
        )
        resource_plan.append(resource_metadata)
        if result_callback is not None:
            result_callback(index, total, pdf_path, resource_metadata)

    for resource in resource_plan:
        resource["resource_tags"] = _deduplicate_tags(resource.get("resource_tags", []))

    _ensure_unique_resource_titles(resource_plan)

    all_tags: list[str] = []
    for resource in resource_plan:
        all_tags.extend(resource.get("resource_tags", []))
    all_tags.extend(["semantic-bridge", "pdf-corpus"])
    dataset_tags = _normalize_tag_list(all_tags)

    inferred_title = dataset_title or f"{pdf_paths[0].parent.name.replace('_', ' ').title()} PDF Corpus"
    inferred_name = dataset_name or slugify(inferred_title) or "semantic-bridge-pdf-corpus"
    dataset_notes_lines = [
        "Dataset registered from a local PDF corpus.",
        f"Document count: {len(pdf_paths)}",
        "Each resource maps to one source PDF.",
    ]

    return {
        "dataset_name": inferred_name,
        "dataset_title": inferred_title,
        "dataset_notes": "\n".join(dataset_notes_lines),
        "dataset_tags": dataset_tags,
        "resources": resource_plan,
    }


def propose_ckan_dataset_metadata_with_llm(
    resource_plan: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    base_url: str | None = None,
    preferred_dataset_name: str | None = None,
    preferred_dataset_title: str | None = None,
    preserve_preferred_values: bool = False,
) -> dict[str, str]:
    """Propose dataset name/title/notes from reviewed resource metadata.

    If ``preserve_preferred_values`` is ``True``, provided preferred values are
    treated as explicit values and are not overwritten by LLM output.
    Otherwise, LLM output is used first and preferred values act as fallback.
    """

    if OpenAI is None:
        raise RuntimeError("openai is not installed in this environment")
    if not resource_plan:
        raise ValueError("resource_plan is empty; cannot propose dataset metadata.")

    sample_resources = []
    for resource in resource_plan[:20]:
        sample_resources.append(
            {
                "resource_name": resource.get("resource_name", ""),
                "resource_title": resource.get("resource_title", ""),
                "resource_tags": resource.get("resource_tags", []),
                "resource_description": _clean_text(resource.get("resource_description", ""), max_chars=240),
            }
        )

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    prompt = (
        "You are proposing CKAN dataset metadata from resource metadata.\n"
        "Return strict JSON with keys: dataset_name, dataset_title, dataset_notes.\n"
        "dataset_name must be lowercase and hyphenated."
    )
    # In unlocked mode, avoid priming the model with preferred values so it can
    # propose corpus-specific metadata instead of echoing defaults.
    payload = {
        "preferred_dataset_name": (preferred_dataset_name or "") if preserve_preferred_values else "",
        "preferred_dataset_title": (preferred_dataset_title or "") if preserve_preferred_values else "",
        "resource_count": len(resource_plan),
        "resources": sample_resources,
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, indent=2)},
        ],
        temperature=0.1,
    )
    parsed = _parse_llm_json(response.choices[0].message.content or "")

    if preserve_preferred_values:
        title_source = preferred_dataset_title or parsed.get("dataset_title") or "Semantic Bridge PDF Corpus"
        name_source = preferred_dataset_name or parsed.get("dataset_name")
    else:
        title_source = parsed.get("dataset_title") or preferred_dataset_title or "Semantic Bridge PDF Corpus"
        name_source = parsed.get("dataset_name") or preferred_dataset_name

    inferred_title = _clean_text(title_source, max_chars=140)
    inferred_name = slugify(str(name_source or inferred_title)) or "semantic-bridge-pdf-corpus"
    inferred_notes = _clean_text(
        parsed.get("dataset_notes")
        or f"Dataset registered from a local PDF corpus. Document count: {len(resource_plan)}. Each resource maps to one source PDF.",
        max_chars=3000,
    )
    return {
        "dataset_name": inferred_name,
        "dataset_title": inferred_title,
        "dataset_notes": inferred_notes,
    }


def create_or_update_ckan_dataset(
    base_url: str,
    *,
    dataset_name: str,
    dataset_title: str,
    dataset_notes: str,
    dataset_tags: list[dict[str, str]] | None = None,
    auth_header: str | None = None,
    owner_org: str | None = None,
    private: bool = False,
    dataset_author: str | None = None,
    dataset_author_email: str | None = None,
    dataset_maintainer: str | None = None,
    dataset_maintainer_email: str | None = None,
    dataset_license_id: str | None = None,
    dataset_url: str | None = None,
    dataset_version: str | None = None,
    dataset_type: str | None = "dataset",
    dataset_isopen: bool | None = None,
    dataset_spatial: str | None = None,
    temporal_coverage_start: str | None = None,
    temporal_coverage_end: str | None = None,
    dataset_extras: list[dict[str, str]] | None = None,
    extra_fields: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Create a new CKAN dataset or patch an existing one."""

    create_payload: dict[str, Any] = {
        "name": dataset_name,
        "title": dataset_title,
        "notes": dataset_notes,
        "private": private,
        "tags": dataset_tags or [],
    }
    if owner_org:
        create_payload["owner_org"] = owner_org
    if dataset_type:
        create_payload["type"] = _clean_text(dataset_type, max_chars=100)
    if dataset_isopen is not None:
        create_payload["isopen"] = bool(dataset_isopen)

    optional_text_fields = {
        "author": dataset_author,
        "author_email": dataset_author_email,
        "maintainer": dataset_maintainer,
        "maintainer_email": dataset_maintainer_email,
        "license_id": dataset_license_id,
        "url": dataset_url,
        "version": dataset_version,
        "spatial": dataset_spatial,
        "temporal_coverage_start": temporal_coverage_start,
        "temporal_coverage_end": temporal_coverage_end,
    }
    for key, value in optional_text_fields.items():
        cleaned = _clean_text(value)
        if cleaned:
            create_payload[key] = cleaned

    if dataset_extras:
        create_payload["extras"] = dataset_extras

    if extra_fields:
        for key, value in extra_fields.items():
            if value is not None:
                create_payload[key] = value

    try:
        existing = fetch_ckan_dataset(base_url, dataset_name, auth_header=auth_header, timeout=timeout)
    except Exception:
        return _ckan_action_post(
            base_url,
            "package_create",
            create_payload,
            auth_header=auth_header,
            timeout=timeout,
        )

    # package_patch often conflicts when owner_org is included; update owner org
    # through its dedicated action only if a change is requested.
    patch_payload = dict(create_payload)
    patch_payload.pop("owner_org", None)

    desired_owner_org = _clean_text(owner_org)
    existing_org = existing.get("organization") if isinstance(existing.get("organization"), dict) else {}
    existing_owner_candidates = {
        _clean_text(existing.get("owner_org")).lower(),
        _clean_text(existing_org.get("id")).lower(),
        _clean_text(existing_org.get("name")).lower(),
        _clean_text(existing_org.get("title")).lower(),
    }
    existing_owner_candidates.discard("")

    if desired_owner_org and desired_owner_org.lower() not in existing_owner_candidates:
        _ckan_action_post(
            base_url,
            "package_owner_org_update",
            {"id": existing["id"], "organization_id": desired_owner_org},
            auth_header=auth_header,
            timeout=timeout,
        )

    patch_payload["id"] = existing["id"]
    return _ckan_action_post(
        base_url,
        "package_patch",
        patch_payload,
        auth_header=auth_header,
        timeout=timeout,
    )


def existing_resources_by_name(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {resource["name"]: resource for resource in dataset.get("resources", [])}


def upload_pdf_resources_to_ckan(
    base_url: str,
    *,
    dataset: dict[str, Any],
    pdf_paths: list[Path],
    resource_plan: list[dict[str, Any]],
    auth_header: str | None = None,
    timeout: int = 180,
) -> list[dict[str, Any]]:
    """Upload or update PDF resources in CKAN using the provided metadata plan."""

    path_by_name = {path.name: path for path in pdf_paths}
    existing_by_name = existing_resources_by_name(dataset)
    uploaded: list[dict[str, Any]] = []

    for resource in resource_plan:
        resource_name = str(resource["resource_name"])
        pdf_path = path_by_name.get(resource_name)
        if pdf_path is None:
            continue

        existing = existing_by_name.get(resource_name)
        payload: dict[str, Any] = {
            "package_id": dataset.get("id") or dataset.get("name"),
            "name": resource_name,
            "description": _clean_text(resource.get("resource_description"), max_chars=3000),
            "format": "PDF",
            "url": resource.get("source_url") or "upload",
        }
        resource_title = _clean_text(resource.get("resource_title"), max_chars=140)
        if resource_title:
            payload["description"] = f"{resource_title}\n\n{payload['description']}"
        mimetype = mimetypes.guess_type(pdf_path.name)[0]
        if mimetype:
            payload["mimetype"] = mimetype
        if existing:
            payload["id"] = existing["id"]
            action = "resource_update"
        else:
            action = "resource_create"

        with pdf_path.open("rb") as handle:
            result = _ckan_action_post(
                base_url,
                action,
                payload,
                auth_header=auth_header,
                files={"upload": handle},
                timeout=timeout,
            )
            uploaded.append(result)

    return uploaded


def register_pdf_corpus_with_ckan(
    corpus_dir: Path,
    *,
    ckan_url: str,
    auth_header: str | None,
    model: str,
    api_key: str,
    base_url: str | None = None,
    dataset_name: str | None = None,
    dataset_title: str | None = None,
    owner_org: str | None = None,
    private: bool = False,
    dataset_author: str | None = None,
    dataset_author_email: str | None = None,
    dataset_maintainer: str | None = None,
    dataset_maintainer_email: str | None = None,
    dataset_license_id: str | None = None,
    dataset_url: str | None = None,
    dataset_version: str | None = None,
    dataset_type: str | None = "dataset",
    dataset_isopen: bool | None = None,
    dataset_spatial: str | None = None,
    temporal_coverage_start: str | None = None,
    temporal_coverage_end: str | None = None,
    dataset_extras: list[dict[str, str]] | None = None,
    extra_fields: dict[str, Any] | None = None,
    max_chars_per_pdf: int = 5000,
) -> dict[str, Any]:
    """Register a local PDF corpus in CKAN with LLM-inferred metadata."""

    pdf_paths = collect_pdf_resources(corpus_dir)
    plan = build_ckan_registration_plan_with_llm(
        pdf_paths,
        model=model,
        api_key=api_key,
        base_url=base_url,
        dataset_name=dataset_name,
        dataset_title=dataset_title,
        max_chars_per_pdf=max_chars_per_pdf,
    )
    dataset = create_or_update_ckan_dataset(
        ckan_url,
        dataset_name=plan["dataset_name"],
        dataset_title=plan["dataset_title"],
        dataset_notes=plan["dataset_notes"],
        dataset_tags=plan["dataset_tags"],
        auth_header=auth_header,
        owner_org=owner_org,
        private=private,
        dataset_author=dataset_author,
        dataset_author_email=dataset_author_email,
        dataset_maintainer=dataset_maintainer,
        dataset_maintainer_email=dataset_maintainer_email,
        dataset_license_id=dataset_license_id,
        dataset_url=dataset_url,
        dataset_version=dataset_version,
        dataset_type=dataset_type,
        dataset_isopen=dataset_isopen,
        dataset_spatial=dataset_spatial,
        temporal_coverage_start=temporal_coverage_start,
        temporal_coverage_end=temporal_coverage_end,
        dataset_extras=dataset_extras,
        extra_fields=extra_fields,
    )
    uploaded_resources = upload_pdf_resources_to_ckan(
        ckan_url,
        dataset=dataset,
        pdf_paths=pdf_paths,
        resource_plan=plan["resources"],
        auth_header=auth_header,
    )
    return {
        "dataset": dataset,
        "uploaded_resources": uploaded_resources,
        "plan": plan,
    }


def _resource_download_url(base_url: str, resource: dict[str, Any]) -> str:
    resource_url = resource.get("url", "")
    if resource_url.startswith(("http://", "https://")):
        return resource_url
    return f"{base_url.rstrip('/')}/{resource_url.lstrip('/')}"


def sync_ckan_resources_to_directory(
    dataset: dict[str, Any],
    target_dir: Path,
    base_url: str,
    auth_header: str | None = None,
    overwrite: bool = False,
    timeout: int = 120,
) -> list[Path]:
    ensure_data_directory(target_dir)
    headers = auth_headers(auth_header)

    downloaded_paths: list[Path] = []
    for resource in dataset.get("resources", []):
        resource_name = resource.get("name", "").strip()
        if not resource_name:
            continue
        suffix = Path(resource_name).suffix.lower()
        if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
            continue

        target_path = target_dir / resource_name
        if target_path.exists() and not overwrite:
            downloaded_paths.append(target_path)
            continue

        response = requests.get(
            _resource_download_url(base_url, resource),
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        target_path.write_bytes(response.content)
        downloaded_paths.append(target_path)

    return downloaded_paths
