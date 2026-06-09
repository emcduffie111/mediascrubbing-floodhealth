"""Decision component visualization helpers."""

from __future__ import annotations

import plotly.graph_objects as go


def plot_component_distribution(component_counts_map: dict[str, int]) -> go.Figure:
    fig = go.Figure(
        [
            go.Bar(
                x=list(component_counts_map.keys()),
                y=list(component_counts_map.values()),
                text=list(component_counts_map.values()),
                textposition="auto",
                marker=dict(color=["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]),
            )
        ]
    )
    fig.update_layout(
        title="Decision Components Identified",
        xaxis_title="Component Type",
        yaxis_title="Count",
        height=400,
    )
    return fig

