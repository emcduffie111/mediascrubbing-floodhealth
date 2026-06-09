"""Notebook-friendly display helpers for the semantic bridge tutorial."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import os
try:
    from IPython.display import Markdown, display
except ImportError:  # pragma: no cover - notebook-only enhancement
    Markdown = None
    display = None


def _render_markdown(text: str) -> None:
    if Markdown is not None and display is not None:
        display(Markdown(text))
    else:
        print(text)


def _escape(text: object) -> str:
    return str(text).replace("_", r"\_")


def resolve_tutorial_dir(
    anchor_filename: str = "2_semantic_bridge_cookbook.ipynb",
    relative_fallback: str = os.getcwd()
) -> Path:
    search_roots = [Path.cwd(), *Path.cwd().parents]
    for root in search_roots:
        if (root / anchor_filename).exists():
            return root
        fallback = root / relative_fallback
        if (fallback / anchor_filename).exists():
            return fallback
    raise FileNotFoundError(f"Could not locate {relative_fallback}")


def print_runtime_paths(tutorial_dir: Path, corpus_dir: Path, raw_dir: Path, cleaned_dir: Path, active_dir: Path) -> None:
    _render_markdown(
        "\n".join(
            [
                "**Runtime Paths**",
                f"- **Tutorial directory:** `{tutorial_dir}`",
                f"- **Corpus directory:** `{corpus_dir}`",
                f"- **Raw source directory:** `{raw_dir}`",
                f"- **Cleaned text directory:** `{cleaned_dir}`",
                f"- **Active input directory:** `{active_dir}`",
            ]
        )
    )


def print_document_list(documents: dict[str, str]) -> None:
    lines = [f"**Loaded Documents:** {len(documents)}"]
    lines.extend(f"- `{filename}`" for filename in documents)
    _render_markdown("\n".join(lines))


def print_document_previews(previews: list[dict[str, str]]) -> None:
    blocks = []
    for preview in previews:
        blocks.append(
            "\n".join(
                [
                    f"### `{_escape(preview['filename'])}`",
                    "```text",
                    preview["preview"],
                    "```",
                ]
            )
        )
    _render_markdown("\n\n".join(blocks))


def print_topic_parameters(n_topics: int, max_vocabulary: int, top_words_display: int) -> None:
    _render_markdown(
        "\n".join(
            [
                "**Topic Model Parameters**",
                f"- **Topics:** {n_topics}",
                f"- **Max vocabulary:** {max_vocabulary}",
                f"- **Display keywords per topic:** {top_words_display}",
            ]
        )
    )


def print_topic_discovery_summary(topics_info: dict[str, dict[str, object]], feature_names, top_words_display: int) -> None:
    lines = [
        "**Topic Discovery Summary**",
        f"- **Vocabulary size:** {len(feature_names)}",
        f"- **Topics discovered:** {len(topics_info)}",
    ]
    for topic_data in topics_info.values():
        lines.append(f"\n### {_escape(topic_data.get('human_label', topic_data['label']))}")
        if topic_data.get("description"):
            lines.append(f"*{topic_data['description']}*")
        lines.append(f"- **Keywords:** {', '.join(topic_data['keywords'][:top_words_display])}")
    _render_markdown("\n".join(lines))


def print_topic_label_comparison(
    baseline_topics_info: dict[str, dict[str, object]],
    relabeled_topics_info: dict[str, dict[str, object]],
    top_words_display: int,
) -> None:
    lines = ["## Topic Label Comparison"]
    for topic_id in baseline_topics_info:
        baseline_topic = baseline_topics_info[topic_id]
        relabeled_topic = relabeled_topics_info[topic_id]
        lines.extend(
            [
                f"\n### {_escape(topic_id)}",
                f"- **Baseline:** {baseline_topic['label']}",
                f"- **Human-readable:** {relabeled_topic.get('human_label', relabeled_topic['label'])}",
                f"- **Description:** {relabeled_topic.get('description', 'No description generated.')}",
                f"- **Keywords:** {', '.join(relabeled_topic['keywords'][:top_words_display])}",
            ]
        )
    _render_markdown("\n".join(lines))


def print_topic_query_recommendations(topic_query_recommendations: list[dict[str, object]]) -> None:
    lines = ["## Topic-to-MINT Query Recommendations"]
    for recommendation in topic_query_recommendations:
        lines.append(f"\n### {_escape(recommendation['label'])}")
        if recommendation.get("description"):
            lines.append(f"*{recommendation['description']}*")
        lines.append(f"- **Suggested MINT domains:** {', '.join(recommendation['query_domains']) or 'None'}")
        lines.append(f"- **Suggested MINT tags:** {', '.join(recommendation['query_tags']) or 'None'}")
    _render_markdown("\n".join(lines))


def print_science_backbone(science_backbone: dict[str, list[str]]) -> None:
    lines = ["## Science Backbone"]
    for domain, subdisciplines in science_backbone.items():
        lines.append(f"\n### {_escape(domain)}")
        for subdiscipline in subdisciplines:
            lines.append(f"- {subdiscipline}")
    _render_markdown("\n".join(lines))


def print_eto_query_recommendations(topic_query_recommendations: list[dict[str, object]]) -> None:
    lines = ["## ETO Map of Science Query Recommendations"]
    for recommendation in topic_query_recommendations:
        lines.append(f"\n### {_escape(recommendation['label'])}")
        if recommendation.get("description"):
            lines.append(f"*{recommendation['description']}*")
        lines.append(f"- **Suggested subjects:** {', '.join(recommendation['subjects']) or 'None'}")
        lines.append(f"- **List view URL:** `{recommendation['eto_list_url']}`")
        lines.append(f"- **Map view URL:** `{recommendation['eto_map_url']}`")
    _render_markdown("\n".join(lines))


def print_topic_mappings(topic_mappings: list[dict[str, object]]) -> None:
    lines = ["## Topic-to-Domain Mappings"]
    for mapping in topic_mappings:
        lines.append(f"\n### {_escape(mapping.get('topic_label', mapping['topic']))}")
        lines.append(f"- **Keywords:** {mapping['keywords']}")
        lines.append(f"- **Primary domain:** {mapping['primary_domain']}")
        if mapping.get("secondary_domain"):
            lines.append(f"- **Secondary domain:** {mapping['secondary_domain']}")
        if mapping.get("eto_matches"):
            lines.append("- **ETO cluster matches:**")
            for match in mapping["eto_matches"]:
                cluster_id = match.get("cluster_id") or "unknown"
                cluster_name = match.get("cluster_name") or "Unnamed cluster"
                lines.append(f"  - `{cluster_id}`: {cluster_name} *(score={match['score']})*")
    _render_markdown("\n".join(lines))


def print_decision_components(decision_components: dict[str, list[dict[str, str]]], preview_limit: int = 5) -> None:
    lines = ["## Decision Components"]
    for component_type, items in decision_components.items():
        lines.append(f"\n### {component_type.title()} *({len(items)} found)*")
        for index, item in enumerate(items[:preview_limit], start=1):
            lines.append(f"{index}. {item['text']} *[{item['source']}]*")
    _render_markdown("\n".join(lines))


def print_svo_vocabulary_preview(svo_vocabulary: dict[str, dict[str, object]], source: str, preview_limit: int = 10) -> None:
    lines = [
        f"**SVO vocabulary source:** {source}",
        f"**Variables available:** {len(svo_vocabulary)}",
    ]
    for svo_name, svo_info in list(svo_vocabulary.items())[:preview_limit]:
        lines.extend(
            [
                f"\n### `{svo_name}`",
                f"- **Label:** {svo_info.get('label', svo_name)}",
                f"- **Standard:** {svo_info['standard_name']}",
                f"- **Units:** {svo_info['units']}",
                f"- **Domain:** {svo_info['domain']}",
            ]
        )
    _render_markdown("\n".join(lines))


def print_svo_mapping_summary(unique_mappings: list[dict[str, str]], preview_limit: int = 6) -> None:
    lines = [f"**Semantic links created:** {len(unique_mappings)}"]
    for index, mapping in enumerate(unique_mappings[:preview_limit], start=1):
        lines.extend(
            [
                f"\n### {index}. *'{mapping['natural_language_term']}'* -> `{mapping['scientific_variable']}`",
                f"- **Standard:** {mapping['standard_name']}",
                f"- **Units:** {mapping['units']}",
                f"- **Domain:** {mapping['domain']}",
                f"- **Data source:** {mapping['data_source']}",
            ]
        )
    _render_markdown("\n".join(lines))


def print_svo_model_recommendations(model_recommendations_df) -> None:
    if model_recommendations_df.empty:
        _render_markdown("*No matching MINT models were found for the current SVO mappings.*")
        return
    lines = [f"**SVO-to-model recommendations:** {len(model_recommendations_df)}"]
    for scientific_variable, group in model_recommendations_df.groupby("scientific_variable", sort=False):
        lines.append(f"\n### `{scientific_variable}`")
        for _, rec in group.sort_values("rank").iterrows():
            lines.append(f"- **{int(rec['rank'])}.** {rec['recommended_model']} *[{rec['model_type']}]*")
            if rec["model_categories"]:
                lines.append(f"  Categories: {rec['model_categories']}")
            if rec["model_description"]:
                lines.append(f"  Why: {rec['model_description'][:180]}")
    _render_markdown("\n".join(lines))


def print_domain_counts(domain_counts: dict[str, int]) -> None:
    lines = [f"**Domains covered:** {len(domain_counts)}"]
    for domain, count in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- **{domain}:** {count}")
    _render_markdown("\n".join(lines))


def print_export_summary(
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    unique_mappings: list[dict[str, str]],
    output_files: dict[str, Path],
    report_path: Path,
) -> None:
    lines = [
        "## Semantic Bridge Analysis Complete",
        f"- **Documents analyzed:** {len(transcripts)}",
        f"- **Topics identified:** {n_topics}",
        f"- **Scientific domains:** {len(set(m['primary_domain'] for m in topic_mappings))}",
        f"- **Decision components:** {sum(len(v) for v in decision_components.values())}",
        f"- **Scientific variables:** {len(set(m['scientific_variable'] for m in unique_mappings))}",
        "- **Output files:**",
    ]
    for path in output_files.values():
        lines.append(f"  - `{path.name}`")
    lines.append(f"  - `{report_path.name}`")
    _render_markdown("\n".join(lines))


def print_report_preview(summary: str, report_path: Path, preview_chars: int = 1000) -> None:
    _render_markdown(
        "\n".join(
            [
                "## Report Preview",
                "```text",
                summary[:preview_chars],
                "...",
                "```",
                f"**Full report:** `{report_path}`",
            ]
        )
    )


def print_ckan_connection_summary(
    *,
    ckan_url: str,
    auth_mode: str,
    owner_org: str | None,
    has_api_token: bool,
    has_username: bool,
    has_password: bool,
) -> None:
    _render_markdown(
        "\n".join(
            [
                "## CKAN Connection Summary",
                f"- **CKAN URL configured:** {bool((ckan_url or '').strip())}",
                f"- **Auth mode:** `{(auth_mode or '').strip() or 'unset'}`",
                f"- **Owner org configured:** {bool((owner_org or '').strip())}",
                f"- **API token configured:** {has_api_token}",
                f"- **Username configured:** {has_username}",
                f"- **Password configured:** {has_password}",
            ]
        )
    )


def print_llm_runtime_summary(
    *,
    model: str,
    has_api_key: bool,
    has_base_url: bool,
) -> None:
    _render_markdown(
        "\n".join(
            [
                "## LLM Runtime Summary",
                f"- **Model:** `{model}`",
                f"- **API key configured:** {has_api_key}",
                f"- **Custom base URL configured:** {has_base_url}",
            ]
        )
    )


def print_ckan_naming_summary(
    *,
    corpus_dir: Path,
    preferred_dataset_name: str | None = None,
    preferred_dataset_title: str | None = None,
    dataset_name_override: str | None,
    dataset_title_override: str | None,
    private_dataset: bool,
) -> None:
    lines = [
        "## Corpus and Naming Summary",
        f"- **Corpus directory:** `{corpus_dir}`",
        f"- **Manual dataset name override:** `{dataset_name_override or 'None'}`",
        f"- **Manual dataset title override:** {dataset_title_override or 'None'}",
        "- **Default dataset naming mode:** LLM-generated from resource metadata",
        f"- **Private dataset:** {private_dataset}",
    ]
    if preferred_dataset_name:
        lines.append(f"- **Preferred dataset name:** `{preferred_dataset_name}`")
    if preferred_dataset_title:
        lines.append(f"- **Preferred dataset title:** {preferred_dataset_title}")
    _render_markdown("\n".join(lines))


def print_pdf_resource_summary(pdf_paths: list[Path], preview_limit: int = 15) -> None:
    lines = [
        "## PDF Discovery Summary",
        f"- **PDF files found:** {len(pdf_paths)}",
    ]
    if pdf_paths:
        lines.append("- **Preview files:**")
        for path in pdf_paths[:preview_limit]:
            lines.append(f"  - `{path.name}`")
        if len(pdf_paths) > preview_limit:
            lines.append(f"  - ... and {len(pdf_paths) - preview_limit} more")
    _render_markdown("\n".join(lines))


def print_ckan_plan_summary(plan: dict[str, Any], preview_limit: int = 10) -> None:
    resources = list(plan.get("resources", []))
    tags = [tag.get("name", "") for tag in plan.get("dataset_tags", []) if isinstance(tag, dict)]
    lines = [
        "## CKAN Plan Summary",
        f"- **Dataset name:** `{plan.get('dataset_name', '')}`",
        f"- **Dataset title:** {plan.get('dataset_title', '')}",
        f"- **Resource metadata entries:** {len(resources)}",
        f"- **Dataset tags:** {', '.join(tags) if tags else 'None'}",
    ]
    if resources:
        lines.append("- **Resource preview:**")
        for index, resource in enumerate(resources[:preview_limit], start=1):
            lines.append(
                f"  - {index}. `{resource.get('resource_name', '')}` -> {resource.get('resource_title', '')}"
            )
        if len(resources) > preview_limit:
            lines.append(f"  - ... and {len(resources) - preview_limit} more")
    _render_markdown("\n".join(lines))


def print_ckan_publish_summary(dataset: dict[str, Any], uploaded_resources: list[dict[str, Any]]) -> None:
    lines = [
        "## CKAN Publish Summary",
        f"- **Dataset ID:** `{dataset.get('id', '')}`",
        f"- **Dataset name:** `{dataset.get('name', '')}`",
        f"- **Resources uploaded/updated:** {len(uploaded_resources)}",
    ]
    if uploaded_resources:
        lines.append("- **Uploaded resources preview:**")
        for resource in uploaded_resources[:15]:
            lines.append(f"  - `{resource.get('name', resource.get('id', 'resource'))}`")
        if len(uploaded_resources) > 15:
            lines.append(f"  - ... and {len(uploaded_resources) - 15} more")
    _render_markdown("\n".join(lines))


def print_ckan_auth_status(has_auth_header: bool) -> None:
    _render_markdown(
        "\n".join(
            [
                "## CKAN Auth Status",
                f"- **Auth header created:** {has_auth_header}",
            ]
        )
    )


def print_ckan_dataset_metadata_summary(dataset_name: str, dataset_title: str, dataset_notes: str) -> None:
    preview = dataset_notes[:240].replace("\n", " ").strip()
    if len(dataset_notes) > 240:
        preview += "…"
    _render_markdown(
        "\n".join(
            [
                "## Dataset Metadata Summary",
                f"- **Dataset name:** `{dataset_name}`",
                f"- **Dataset title:** {dataset_title}",
                f"- **Dataset notes preview:** {preview or 'None'}",
            ]
        )
    )


def launch_ckan_plan_editor(plan: dict[str, Any]) -> dict[str, Any] | None:
    """Launch an interactive editor for CKAN plan metadata in notebooks.

    The editor updates the provided ``plan`` object in place.
    """

    try:
        import ipywidgets as widgets
    except Exception as exc:
        print("ipywidgets is required for the interactive editor.")
        print("Install with: python -m pip install ipywidgets")
        print(f"Reason: {exc}")
        return None

    if not isinstance(plan, dict):
        raise TypeError("plan must be a dictionary")

    plan.setdefault("dataset_name", "")
    plan.setdefault("dataset_title", "")
    plan.setdefault("dataset_notes", "")
    plan.setdefault("resources", [])

    dataset_name_input = widgets.Text(
        description="Name",
        value=str(plan.get("dataset_name", "")),
        layout=widgets.Layout(width="100%"),
    )
    dataset_title_input = widgets.Text(
        description="Title",
        value=str(plan.get("dataset_title", "")),
        layout=widgets.Layout(width="100%"),
    )
    dataset_notes_input = widgets.Textarea(
        description="Notes",
        value=str(plan.get("dataset_notes", "")),
        layout=widgets.Layout(width="100%", height="120px"),
    )

    resource_options = [
        (f"{index}: {item.get('resource_name', 'resource')}", index)
        for index, item in enumerate(plan["resources"])
    ]
    resource_selector = widgets.Dropdown(
        options=resource_options,
        description="Resource",
        disabled=(len(resource_options) == 0),
        layout=widgets.Layout(width="100%"),
    )

    resource_title_input = widgets.Text(
        description="Res Title",
        layout=widgets.Layout(width="100%"),
    )
    resource_tags_input = widgets.Text(
        description="Tags",
        layout=widgets.Layout(width="100%"),
    )
    resource_desc_input = widgets.Textarea(
        description="Res Desc",
        layout=widgets.Layout(width="100%", height="140px"),
    )

    status = widgets.HTML(value="<i>Editor ready.</i>")
    preview_out = widgets.Output()

    def _load_resource(index: int | None) -> None:
        if index is None or index >= len(plan["resources"]):
            return
        resource = plan["resources"][index]
        resource_title_input.value = str(resource.get("resource_title", ""))
        resource_desc_input.value = str(resource.get("resource_description", ""))
        resource_tags_input.value = ", ".join(resource.get("resource_tags", []))

    def _on_resource_change(change: dict[str, Any]) -> None:
        if change.get("name") == "value":
            _load_resource(change["new"])

    def _refresh_preview(*_args: Any) -> None:
        with preview_out:
            preview_out.clear_output()
            print("Current dataset fields:")
            print("- name:", plan.get("dataset_name", ""))
            print("- title:", plan.get("dataset_title", ""))
            notes = plan.get("dataset_notes", "")
            notes_preview = notes[:180] + ("…" if len(notes) > 180 else "")
            print("- notes:", notes_preview)
            print("\nResource preview (first 10):")
            for index, resource in enumerate(plan.get("resources", [])[:10]):
                tags = ", ".join(resource.get("resource_tags", [])[:6])
                print(f"{index}. {resource.get('resource_name', 'resource')} | {resource.get('resource_title', '')} | {tags}")

    def _apply_dataset(_btn: Any) -> None:
        plan["dataset_name"] = dataset_name_input.value.strip()
        plan["dataset_title"] = dataset_title_input.value.strip()
        plan["dataset_notes"] = dataset_notes_input.value.strip()
        status.value = "<b>Dataset fields updated.</b>"
        _refresh_preview()

    def _apply_resource(_btn: Any) -> None:
        index = resource_selector.value
        if index is None or index >= len(plan["resources"]):
            status.value = "<b>No resource selected.</b>"
            return
        resource = plan["resources"][index]
        resource["resource_title"] = resource_title_input.value.strip()
        resource["resource_description"] = resource_desc_input.value.strip()
        resource["resource_tags"] = [tag.strip() for tag in resource_tags_input.value.split(",") if tag.strip()]
        status.value = f"<b>Resource {index} updated.</b>"
        _refresh_preview()

    resource_selector.observe(_on_resource_change, names="value")
    if resource_options:
        _load_resource(resource_selector.value)

    apply_dataset_btn = widgets.Button(description="Apply Dataset Fields", button_style="primary")
    apply_resource_btn = widgets.Button(description="Apply Resource Fields", button_style="info")
    refresh_preview_btn = widgets.Button(description="Refresh Preview")

    apply_dataset_btn.on_click(_apply_dataset)
    apply_resource_btn.on_click(_apply_resource)
    refresh_preview_btn.on_click(_refresh_preview)

    dataset_box = widgets.VBox(
        [
            widgets.HTML("<h4>Dataset Metadata</h4>"),
            dataset_name_input,
            dataset_title_input,
            dataset_notes_input,
            apply_dataset_btn,
        ]
    )
    resource_box = widgets.VBox(
        [
            widgets.HTML("<h4>Resource Metadata</h4>"),
            resource_selector,
            resource_title_input,
            resource_tags_input,
            resource_desc_input,
            apply_resource_btn,
        ]
    )

    display(
        widgets.VBox(
            [
                widgets.HBox([dataset_box, resource_box], layout=widgets.Layout(align_items="flex-start")),
                widgets.HBox([refresh_preview_btn]),
                status,
                preview_out,
            ]
        )
    )
    _refresh_preview()

    return {
        "dataset_name_input": dataset_name_input,
        "dataset_title_input": dataset_title_input,
        "dataset_notes_input": dataset_notes_input,
        "resource_selector": resource_selector,
        "resource_title_input": resource_title_input,
        "resource_tags_input": resource_tags_input,
        "resource_desc_input": resource_desc_input,
    }


def build_ckan_plan_with_progress(
    sbp_api,
    *,
    pdf_paths: list[Path],
    model: str,
    api_key: str,
    base_url: str | None = None,
    dataset_name: str | None = None,
    dataset_title: str | None = None,
    print_result_preview: bool = True,
) -> dict[str, Any]:
    """Build CKAN resource metadata plan with notebook progress UI and per-file logs."""

    progress_widget = None
    status_widget = None

    try:
        import ipywidgets as widgets

        progress_widget = widgets.IntProgress(
            value=0,
            min=0,
            max=len(pdf_paths),
            description="LLM",
            bar_style="info",
        )
        status_widget = widgets.HTML(value="Starting resource metadata generation...")
        display(widgets.VBox([progress_widget, status_widget]))

        def _progress_callback(index: int, total: int, pdf_path: Path) -> None:
            progress_widget.max = total
            progress_widget.value = index
            status_widget.value = f"<code>{index}/{total}</code> {pdf_path.name}"

    except Exception:
        def _progress_callback(index: int, total: int, pdf_path: Path) -> None:
            print(f"[{index}/{total}] {pdf_path.name}")

    def _result_callback(index: int, total: int, pdf_path: Path, metadata: dict[str, Any]) -> None:
        if not print_result_preview:
            return
        title = metadata.get("resource_title", "")
        tags = ", ".join(metadata.get("resource_tags", [])[:8])
        desc = str(metadata.get("resource_description", "")).replace("\n", " ").strip()
        if len(desc) > 160:
            desc = desc[:159].rstrip() + "…"
        print(f"✓ {index}/{total} {pdf_path.name}")
        print(f"  title: {title}")
        print(f"  tags: {tags}")
        print(f"  desc: {desc}")

    plan = sbp_api.build_ckan_registration_plan_with_llm(
        pdf_paths=pdf_paths,
        model=model,
        api_key=api_key,
        base_url=base_url or None,
        dataset_name=dataset_name,
        dataset_title=dataset_title,
        progress_callback=_progress_callback,
        result_callback=_result_callback,
    )

    if progress_widget is not None:
        progress_widget.bar_style = "success"
    if status_widget is not None:
        status_widget.value = "Resource metadata generation complete."

    return plan
