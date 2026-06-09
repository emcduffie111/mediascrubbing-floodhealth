"""SVO visualization helpers."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from semantic_bridge.mapping.svo import domain_counts


def plot_svo_sunburst(unique_mappings: list[dict[str, str]]) -> tuple[pd.DataFrame, go.Figure, dict[str, int]]:
    counts = domain_counts(unique_mappings)
    sunburst_data = []
    for mapping in unique_mappings:
        sunburst_data.append(
            {
                "labels": mapping["scientific_variable"],
                "parents": mapping["domain"],
                "values": 1,
            }
        )
    for domain, count in counts.items():
        sunburst_data.append({"labels": domain, "parents": "", "values": count})
    df_sunburst = pd.DataFrame(sunburst_data)
    fig = px.sunburst(
        df_sunburst,
        names="labels",
        parents="parents",
        values="values",
        title="Scientific Variables by Domain",
        height=500,
    )
    return df_sunburst, fig, counts

