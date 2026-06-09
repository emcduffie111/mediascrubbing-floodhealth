"""Topic visualization helpers."""

from __future__ import annotations

import plotly.graph_objects as go

from semantic_bridge.text.topics import build_topic_distribution_frame, topic_display_name


def plot_topic_distribution(
    doc_topic_dist,
    doc_names: list[str],
    topics_info: dict[str, dict[str, object]],
    n_topics: int,
):
    topic_df = build_topic_distribution_frame(doc_topic_dist, doc_names, n_topics)

    fig = go.Figure()
    for topic_num in topic_df.columns:
        topic_info = topics_info[topic_num]
        display_name = topic_display_name(topic_info)
        hover_text = [
            f"{display_name}<br>"
            f"Document: {doc}<br>"
            f"Proportion: {val:.1%}<br>"
            f"Keywords: {', '.join(topic_info['keywords'][:6])}"
            + (f"<br>Description: {topic_info['description']}" if topic_info.get("description") else "")
            for doc, val in zip(topic_df.index, topic_df[topic_num])
        ]
        fig.add_trace(
            go.Bar(
                name=display_name,
                x=topic_df.index,
                y=topic_df[topic_num],
                text=[f"{val:.1%}" for val in topic_df[topic_num]],
                textposition="auto",
                hovertext=hover_text,
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=f"Topic Distribution Across Documents ({n_topics} Topics)",
        xaxis_title="Document",
        yaxis_title="Topic Proportion",
        barmode="stack",
        height=500,
        legend=dict(
            title="Topics (hover for details)",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
        ),
    )
    return topic_df, fig

