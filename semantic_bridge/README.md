# `semantic_bridge`

`semantic_bridge` is a lightweight Python library for turning mixed document corpora into:

- topic structures,
- domain mappings,
- decision-analysis components,
- semantic variable links (SVO-style),
- and optional CKAN-ready dataset/resource metadata.

It is designed to support the DSO Institute tutorial notebooks and scripts in this directory.

## What This Package Does

At a high level, the package implements a pipeline:

1. Load and normalize documents from disk.
2. Preprocess and model latent topics from text.
3. Map topics to scientific domains (built-in keywords, ETO export, or MINT-derived hints).
4. Extract decision components (goals, objectives, variables, constraints, indicators).
5. Build semantic links from natural-language terms to scientific variables.
6. Visualize and export results.
7. Optionally register a PDF corpus into CKAN with LLM-assisted metadata.

## Package Layout

```text
semantic_bridge/
  __init__.py
  api.py                    # Public re-export surface
  constants.py              # Default backbones, keywords, patterns, sample docs
  types.py                  # Shared type aliases
  analysis/
    decision_components.py  # Decision component extraction + presentation table
  io/
    documents.py            # Document loading, OCR, previews, stats
    ckan.py                 # CKAN auth, dataset/resource sync, LLM metadata
  text/
    preprocess.py           # Text normalization
    topics.py               # Topic discovery + summaries
    llm_labels.py           # LLM relabeling and readability rewrite
  mapping/
    domains.py              # Keyword-based topic-to-domain mapping
    svo.py                  # SVO mapping and de-duplication
    eto.py                  # ETO URL/query/export helpers and cluster mapping
    mint.py                 # MINT vocabulary/model retrieval and recommendations
  viz/
    network.py              # Network graph of domains, subdisciplines, topics
    topics.py               # Stacked topic distribution bar chart
    components.py           # Decision component bar chart
    svo.py                  # SVO domain/variable sunburst
  export/
    tables.py               # CSV/HTML outputs and quick-reference table
    reports.py              # Markdown summary report
  notebook/
    display.py              # Notebook-oriented markdown/UI rendering helpers
```

## Primary Entry Point

Use the package through:

```python
from semantic_bridge import api as sbp
```

`semantic_bridge.api` re-exports the operational functions from all modules so notebook users can call one namespace.

## Runtime Dependencies

Core dependencies implied by imports:

- `pandas`
- `scikit-learn`
- `nltk`
- `plotly`
- `networkx`
- `requests`
- `pypdf`
- `python-docx`
- `Pillow`

Optional dependencies by feature:

- `openai` for LLM-assisted topic/component/CKAN metadata helpers.
- `pytesseract` (plus system `tesseract`) for image OCR.
- `ipywidgets` for interactive CKAN plan editor in notebooks.
- `IPython` for rich markdown display in notebooks.
- `ckanapi` for the standalone corpus registration script.

## Core Data Contracts

Defined in `types.py`:

- `DocumentMap`: `dict[str, str]` (filename to text).
- `TopicInfoMap`: `dict[str, dict[str, Any]]` (e.g., `Topic 1` metadata).
- `DecisionComponents`: `dict[str, list[dict[str, str]]]`.
- `SVOMapping`: mapping row for semantic variable links.

Common topic format:

```python
{
  "Topic 1": {
    "label": "Topic 1: groundwater, aquifer, pumping",
    "keywords": ["groundwater", "aquifer", "pumping", "..."],
    "human_label": "Topic 1: Groundwater Management",   # optional (LLM)
    "description": "Short human-readable explanation"   # optional (LLM)
  }
}
```

## End-to-End Usage (Programmatic)

```python
from pathlib import Path
import spacy
from semantic_bridge import api as sbp

data_dir = Path("data/subsidence_groundwater_corpus")
documents = sbp.load_documents(data_dir)

processed_docs, doc_names = sbp.preprocess_documents(documents)
topic_result = sbp.discover_topics(processed_docs, n_topics=6, max_vocabulary=1500)
topics_info = topic_result["topics_info"]

topic_mappings = sbp.map_topics_to_domains(topics_info)

nlp = spacy.load("en_core_web_sm")
decision_components = sbp.extract_decision_components(documents, nlp)
components_df = sbp.component_table(decision_components)

svo_vocab = sbp.default_svo_vocabulary()
svo_mappings = sbp.create_svo_mappings(documents, svo_vocab)
unique_svo = sbp.deduplicate_svo_mappings(svo_mappings)
svo_df = sbp.svo_table(unique_svo)

graph, network_fig = sbp.create_network_figure(
    sbp.default_science_backbone(), topic_mappings, case_study_name="demo"
)
_, topic_fig = sbp.plot_topic_distribution(
    topic_result["doc_topic_dist"], doc_names, topics_info, n_topics=6
)
_, sunburst_fig, _ = sbp.plot_svo_sunburst(unique_svo)
```

## Module-by-Module Reference

### `io.documents`

Purpose: file ingestion and corpus inspection.

Key functions:

- `load_documents(data_dir)`: loads from `cleaned/` then `raw/` when those dirs exist; otherwise scans `data_dir`.
- `load_document(path)`: dispatches by suffix.
- `preview_documents(documents, preview_chars=200)`: short previews.
- `build_stats_table(documents)`: characters, words, sentence count.
- `write_sample_documents(data_dir, sample_transcripts=None)`: writes canned sample transcripts.

Supported suffixes:

- `.txt`, `.json`, `.docx`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`

Behavior details:

- Hidden paths (`.ipynb_checkpoints`, etc.) are skipped.
- Duplicate filenames are kept from first root encountered (`cleaned` wins over `raw`).
- JSON loaders prefer top-level keys in order: `text`, `content`, `body`, `description`.
- OCR requires `pytesseract`; otherwise image load raises `RuntimeError`.

### `text.preprocess`

Purpose: lowercase/normalize text and optional stopword filtering.

Key functions:

- `preprocess_text(text, custom_stopwords=None)`: removes non-letter chars and applies custom stopwords.
- `preprocess_documents(documents, custom_stopwords=None)`: returns `(processed_docs, doc_names)` in insertion order.

### `text.topics`

Purpose: topic discovery and summary tables.

Key functions:

- `discover_topics(processed_docs, n_topics, max_vocabulary, topic_keyword_count=8, custom_stopwords=None)`
- `build_topic_summary(topics_info, doc_topic_dist, top_words_display)`
- `topic_display_name(topic_info)`: prefers `human_label` over raw `label`.
- `build_topic_distribution_frame(doc_topic_dist, doc_names, n_topics)`

Implementation notes:

- Uses `TfidfVectorizer` with n-grams `(1, 2)`.
- Uses `LatentDirichletAllocation` (`random_state=42`, `max_iter=20`).

### `mapping.domains`

Purpose: keyword overlap topic-to-domain mapping.

Key function:

- `map_topics_to_domains(topics_info, domain_keywords=None)`

Defaults:

- `DEFAULT_DOMAIN_KEYWORDS` from `constants.py`.

Returned mapping fields:

- `topic`, `topic_label`, `keywords`, `primary_domain`, `secondary_domain`.

### `analysis.decision_components`

Purpose: extract decision-analysis phrase candidates from sentences and noun chunks.

Key functions:

- `extract_decision_components(documents, nlp, patterns=None, component_seeds=None, keyword_weight=0.45, semantic_weight=0.55)`
- `component_counts(decision_components)`
- `component_table(decision_components)`
- `human_readable_component_table(components_df, prefer_readable_text=True, max_context_chars=None)`

Component families:

- `goals`, `objectives`, `variables`, `constraints`, `indicators`

Scoring model:

- Base confidence = `keyword_weight + semantic_weight * similarity`.
- Similarity uses vector similarity when available; lexical Jaccard fallback when vectors are unavailable.
- Duplicate phrase texts are deduplicated by highest confidence and truncated to top 50 per component type.

Presentation helper:

- `human_readable_component_table` cleans HTML/noise and can use `readable_text` / `readable_rationale` columns if they exist.

### `text.llm_labels`

Purpose: LLM post-processing for readability and interpretability.

Key functions:

- `relabel_topics_with_llm(topics_info, doc_topic_dist, doc_names, documents, model, api_key, base_url=None)`
- `improve_decision_component_readability_with_llm(components_df, model, api_key, base_url=None, temperature=0.1)`

Notes:

- Requires `openai` package.
- Both functions parse model output with defensive JSON extraction.
- Topic relabeling appends labels as `"{topic_id}: {label}"` in `human_label`.

### `mapping.svo`

Purpose: connect natural-language mentions to a scientific variable vocabulary.

Key functions:

- `create_svo_mappings(documents, svo_vocabulary, min_keyword_words=2, allow_single_word_keywords=None)`
- `deduplicate_svo_mappings(svo_mappings)`
- `svo_table(unique_mappings)`

Matching behavior:

- Case-insensitive string containment search over raw document text.
- By default ignores one-word keywords (`min_keyword_words=2`) unless explicitly allowed.
- Stores first sentence containing match as `context` (truncated to 150 chars).

### `mapping.eto`

Purpose: generate ETO map queries, parse ETO exports, build reusable science-backbone layers, and project topics or keyword groups onto that backbone.

Key constants/functions:

- `ETO_MAP_BASE_URL`
- `build_eto_map_url(subjects=None, mode="list", extra_params=None)`
- `recommend_eto_queries_for_topics(topics_info, keywords_per_topic=3)`
- `prepare_eto_query_exports(output_dir, topics_info, keywords_per_topic=3)`
- `load_eto_cluster_export(csv_path)`
- `build_science_backbone_from_eto_export(cluster_df)`
- `build_eto_science_backbone(cluster_df, ...)`
- `materialize_ucsd_scaffold(scaffold=None)`
- `merge_science_backbone_layers(eto_layer, base_layer)`
- `build_science_backbone_payload(...)`
- `selected_science_backbone(payload)`
- `write_science_backbone_payload(payload, output_path)`
- `read_science_backbone_payload(path)`
- `map_keyword_groups_to_backbone(keyword_groups, backbone, ...)`
- `project_documents_onto_backbone(documents, keyword_groups, group_mappings)`
- `map_topics_to_eto_clusters(topics_info, cluster_df, top_matches=3)`

CSV handling highlights:

- Column matching is case-insensitive and flexible (`Top Discipline`, `Cluster Name`, etc.).
- Multi-valued cells can split on `|`, `;`, `,`, or long whitespace sequences.
- Current ETO field-oriented exports can be mapped into a UCSD-style science backbone with terms, source metadata, cluster summaries, and citations.
- `build_science_backbone_from_eto_export` keeps the legacy `dict[str, list[str]]` shape by default; pass `rich=True` for the richer node structure.

### `mapping.mint`

Purpose: retrieve MINT variables/models and produce recommendation tables.

Key functions:

- `fetch_mint_svo_vocabulary(base_url, username="mint@isi.edu", per_page=200, max_pages=3, timeout=30)`
- `fetch_mint_model_candidates(base_url, username="mint@isi.edu", per_page=100, max_pages=3, timeout=30)`
- `recommend_models_for_svo_mappings(unique_mappings, model_candidates, recommendations_per_svo=2, scientific_variables=None)`
- `recommend_mint_queries_for_topics(topics_info, model_candidates, domains_per_topic=3, tags_per_topic=5)`

Normalization behavior:

- Handles multiple payload shapes (`items`, `results`, `data`, etc.).
- Uses URI tail decoding and humanization for labels.
- Builds `searchable_text` for simple scoring/ranking.

### `io.ckan`

Purpose: CKAN auth, dataset create/update, resource sync, and LLM-assisted corpus registration.

Authentication helpers:

- `build_ckan_auth_header(auth_mode, api_token=None, username=None, password=None, tapis_url=DEFAULT_TAPIS_URL)`
- `get_tapis_token(username, password, tapis_url=DEFAULT_TAPIS_URL)`
- `auth_headers(auth_header=None)`

Dataset/resource API helpers:

- `fetch_ckan_dataset(base_url, dataset_name, auth_header=None, timeout=60)`
- `create_or_update_ckan_dataset(...)`
- `existing_resources_by_name(dataset)`
- `upload_pdf_resources_to_ckan(base_url, dataset, pdf_paths, resource_plan, auth_header=None, timeout=180)`
- `sync_ckan_resources_to_directory(dataset, target_dir, base_url, auth_header=None, overwrite=False, timeout=120)`

LLM metadata helpers:

- `extract_ckan_resource_metadata_with_llm(pdf_path, model, api_key, base_url=None, max_chars=5000, temperature=0.1)`
- `build_ckan_registration_plan_with_llm(pdf_paths, model, api_key, ...)`
- `propose_ckan_dataset_metadata_with_llm(resource_plan, model, api_key, ..., preserve_preferred_values=False)`
- `register_pdf_corpus_with_ckan(corpus_dir, ckan_url, auth_header, model, api_key, ...)`

Operational details:

- CKAN action POST wrappers raise clear `ValueError` messages for non-2xx or CKAN error payloads.
- `create_or_update_ckan_dataset` uses:
  - `package_create` when missing,
  - `package_owner_org_update` when org changes,
  - `package_patch` for updates.
- PDF plan generation sends one LLM request per PDF.
- Resource title collisions are auto-disambiguated by appending filename stem.

Debugging:

- Set `CKAN_DEBUG=1` (or `true/yes/on/debug`) to log sanitized request/response payloads.

### `viz.*`

Purpose: plotly/networkx visual outputs.

Functions:

- `viz.network.create_network_figure(science_backbone, topic_mappings, case_study_name)`
- `viz.topics.plot_topic_distribution(doc_topic_dist, doc_names, topics_info, n_topics)`
- `viz.components.plot_component_distribution(component_counts_map)`
- `viz.svo.plot_svo_sunburst(unique_mappings)`

### `export.*`

Purpose: write outputs and report artifacts.

Functions:

- `export.tables.write_outputs_table(output_dir, case_study_name, topic_mappings, components_df, svo_df, network_fig, sunburst_fig)`
- `export.tables.build_quick_reference(...)`
- `export.reports.build_summary_report(...)`
- `export.reports.write_report(output_dir, case_study_name, summary)`

Generated artifacts include CSVs, HTML visualizations, and markdown report text.

### `notebook.display`

Purpose: notebook-friendly rendering and CKAN workflow widgets.

Key categories:

- Runtime/doc inspection: `print_runtime_paths`, `print_document_list`, `print_document_previews`.
- Topic/component/SVO summaries: `print_topic_discovery_summary`, `print_decision_components`, `print_svo_mapping_summary`, etc.
- CKAN summaries: `print_ckan_connection_summary`, `print_ckan_plan_summary`, `print_ckan_publish_summary`, etc.
- Interactive editing: `launch_ckan_plan_editor(plan)` (requires `ipywidgets`).
- Progress-tracked plan building: `build_ckan_plan_with_progress(...)`.

Important path behavior:

- `resolve_tutorial_dir()` searches for `semantic_bridge_cookbook.ipynb` and has a fallback path currently pointing to `DSO-Institute-2026/Day-3/Morning`.

## Defaults and Seed Data

`constants.py` provides:

- `DEFAULT_SCIENCE_BACKBONE`
- `DEFAULT_DOMAIN_KEYWORDS`
- `DEFAULT_COMPONENT_PATTERNS`
- `DEFAULT_COMPONENT_SEED_PHRASES`
- `DEFAULT_SVO_VOCABULARY`
- `SAMPLE_TRANSCRIPTS`

Use copy-safe helpers when you want mutable working versions:

- `default_science_backbone()`
- `default_svo_vocabulary()`

## CKAN Registration Script

Parent directory script:

- `register_semantic_bridge_corpus_ckan.py`

What it does:

1. Reads seed URL CSV + download manifest CSV.
2. Resolves cleaned corpus files.
3. Creates/patches dataset.
4. Uploads each file as CKAN resource.

Helpful flags:

- `--ckan-url`
- `--auth-mode` (`api_token` or `tapis_password`)
- `--owner-org`
- `--dataset-name`, `--dataset-title`, `--dataset-notes`
- `--private`
- `--dry-run`

## Test Coverage Snapshot

Tests are under `../tests/` and currently validate:

- document loading precedence and JSON extraction behavior,
- preprocessing and topic/domain mapping basic contracts,
- decision component extraction and confidence dedupe behavior,
- CKAN helper auth/CRUD/upload flows with monkeypatched clients,
- MINT/ETO normalization and scoring helpers,
- LLM readability rewrite integration behavior,
- report generation and minimal module shims.

Run tests from `Day-2/Morning`:

```bash
pytest -q
```

## Common Pitfalls

- Missing optional packages will break feature-specific paths (`openai`, `pytesseract`, `ipywidgets`, `ckanapi`).
- OCR requires both Python binding and system Tesseract installation.
- SVO matching defaults to multi-word keywords; include `allow_single_word_keywords` for one-word terms.
- CKAN auth header mode must match your server expectations (`Authorization: token` vs `Bearer ...`).

## Minimal Quickstart Checklist

1. Install core dependencies and optional ones needed for your workflow.
2. Ensure NLTK tokenizers and any NLP model requirements are available.
3. Start with `from semantic_bridge import api as sbp`.
4. Use `load_documents -> preprocess_documents -> discover_topics`.
5. Add decision/SVO/visual/export steps based on your tutorial objective.
