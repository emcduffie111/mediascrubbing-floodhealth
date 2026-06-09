"""Tabular export helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_outputs_table(output_dir: Path, case_study_name: str, topic_mappings, components_df, svo_df, network_fig, sunburst_fig):
    mapping_path = output_dir / f"{case_study_name}_topic_mappings.csv"
    components_path = output_dir / f"{case_study_name}_components.csv"
    svo_path = output_dir / f"{case_study_name}_svo_mappings.csv"
    network_path = output_dir / f"{case_study_name}_network.html"
    sunburst_path = output_dir / f"{case_study_name}_svo_sunburst.html"

    pd.DataFrame(topic_mappings).to_csv(mapping_path, index=False)
    components_df.to_csv(components_path, index=False)
    svo_df.to_csv(svo_path, index=False)
    network_fig.write_html(str(network_path))
    sunburst_fig.write_html(str(sunburst_path))

    return {
        "mapping_path": mapping_path,
        "components_path": components_path,
        "svo_path": svo_path,
        "network_path": network_path,
        "sunburst_path": sunburst_path,
    }


def build_quick_reference(
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    svo_vocabulary: dict[str, dict[str, object]],
    unique_mappings: list[dict[str, str]],
    output_files: dict[str, Path],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Analysis Component": [
                "Input Documents",
                "Topics Discovered",
                "Scientific Domains",
                "Decision Components",
                "Scientific Variables",
                "Semantic Links",
            ],
            "Count": [
                len(transcripts),
                n_topics,
                len(set(mapping["primary_domain"] for mapping in topic_mappings)),
                sum(len(value) for value in decision_components.values()),
                len(svo_vocabulary),
                len(unique_mappings),
            ],
            "Output File": [
                "N/A",
                output_files["mapping_path"].name,
                output_files["network_path"].name,
                output_files["components_path"].name,
                output_files["svo_path"].name,
                output_files["svo_path"].name,
            ],
        }
    )

