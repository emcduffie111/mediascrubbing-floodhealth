"""Network visualization helpers.

This module contains the reusable pieces that were previously living in the
Day 2 notebook Section 10. The notebook should only call these functions rather
than defining graph builders inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import os

import networkx as nx
import plotly.graph_objects as go


def _subdisciplines(node: Any) -> list[str]:
    if isinstance(node, dict):
        return list(node.get("subdisciplines") or node.get("subs") or ["General"])
    if isinstance(node, list):
        return list(node)
    return ["General"]


def _as_records(value: Any) -> list[dict[str, Any]]:
    """Accept list-of-dicts or pandas DataFrame."""
    if hasattr(value, "to_dict"):
        return value.to_dict("records")
    return list(value or [])


def create_network_figure(
    science_backbone: dict[str, object],
    topic_mappings: list[dict[str, object]],
    case_study_name: str,
) -> tuple[nx.Graph, go.Figure]:
    """Original lightweight Plotly diagnostic network."""
    graph = nx.Graph()
    for domain in science_backbone:
        graph.add_node(domain, node_type="domain")
    for domain, node in science_backbone.items():
        for sub in _subdisciplines(node):
            graph.add_node(sub, node_type="subdiscipline")
            graph.add_edge(domain, sub)
    for mapping in topic_mappings:
        topic = mapping.get("topic_label") or mapping["topic"]
        graph.add_node(topic, node_type="topic")
        graph.add_edge(mapping["primary_domain"], topic)

    pos = nx.spring_layout(graph, k=2, iterations=50, seed=42)

    edge_trace = go.Scatter(
        x=[],
        y=[],
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )
    for edge in graph.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace["x"] += (x0, x1, None)
        edge_trace["y"] += (y0, y1, None)

    colors = {"domain": "#FF6B6B", "subdiscipline": "#4ECDC4", "topic": "#FFE66D"}
    sizes = {"domain": 20, "subdiscipline": 15, "topic": 12}

    node_traces = []
    for node_type in ["domain", "subdiscipline", "topic"]:
        nodes = [n for n, data in graph.nodes(data=True) if data.get("node_type") == node_type]
        node_traces.append(
            go.Scatter(
                x=[pos[n][0] for n in nodes],
                y=[pos[n][1] for n in nodes],
                mode="markers+text",
                text=nodes,
                textposition="top center",
                marker=dict(size=sizes[node_type], color=colors[node_type]),
                name=node_type.title(),
            )
        )

    fig = go.Figure(
        data=[edge_trace] + node_traces,
        layout=go.Layout(
            title=f"Science Backbone Network with Topics ({case_study_name})",
            showlegend=True,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600,
        ),
    )
    return graph, fig


def build_semantic_bridge_graph(
    science_backbone: dict[str, Any],
    topic_mappings: list[dict[str, Any]],
    *,
    max_subdisciplines_per_domain: int = 15,
    include_candidate_domain_edges: bool = True,
    only_topic_linked: bool = True,
    keep_linked_domain_subdisciplines: bool = True,
) -> nx.Graph:
    """Build a reusable NetworkX graph for the Semantic Bridge visualization.

    Constructs a graph representing the relationship between discovered topics and
    the scientific disciplines defined in the science backbone.

    Args:
        science_backbone: The filtered science backbone dictionary.
        topic_mappings: List of topic mapping records.
        max_subdisciplines_per_domain: Limit the number of subdisciplines shown for clarity.
        include_candidate_domain_edges: If True, draw dashed lines to secondary/candidate domains.
        only_topic_linked: If True, remove backbone domains that have no associated topics.
        keep_linked_domain_subdisciplines: If True, keep subdiscipline nodes for context 
            under domains that are linked to topics.

    Returns:
        A NetworkX Graph object with node metadata for visualization.


    Topic mappings can include ``candidate_domains``. When present, the graph
    draws lighter edges to candidate domains in addition to the primary-domain
    edge. This makes the topic/domain coverage visible instead of collapsing the
    visual layer to only primary domains.
    """
    graph = nx.Graph()
    mappings = _as_records(topic_mappings)

    # 1. Determine which domains are linked to topics
    linked_domains = set()
    for mapping in mappings:
        primary = mapping.get("primary_domain") or mapping.get("domain")
        if primary:
            linked_domains.add(primary)

        secondary = mapping.get("secondary_domain")
        if secondary:
            linked_domains.add(secondary)

        candidates = mapping.get("candidate_domains", []) or []
        for cand in candidates:
            if isinstance(cand, dict):
                d = cand.get("domain")
                if d:
                    linked_domains.add(d)

    for domain, node in science_backbone.items():
        # 2. Filter domains if only_topic_linked=True
        if only_topic_linked and domain not in linked_domains:
            continue

        domain_id = f"domain::{domain}"
        subdisciplines = _subdisciplines(node)

        graph.add_node(
            domain_id,
            label=domain,
            title=f"<b>{domain}</b><br>{len(subdisciplines)} subdisciplines",
            group="Discipline",
            node_type="discipline",
            domain=domain,
            size=28,
            color="#2563eb",
        )

        # 3. Add subdisciplines if requested
        if keep_linked_domain_subdisciplines:
            for subdiscipline in subdisciplines[:max_subdisciplines_per_domain]:
                sub_id = f"subdiscipline::{domain}::{subdiscipline}"

                graph.add_node(
                    sub_id,
                    label=subdiscipline,
                    title=f"<b>{subdiscipline}</b><br>Domain: {domain}",
                    group="Subdiscipline",
                    node_type="subdiscipline",
                    domain=domain,
                    size=12,
                    color="#64748b",
                )

                graph.add_edge(
                    domain_id,
                    sub_id,
                    title="contains",
                    edge_type="contains",
                    color="#cbd5e1",
                    width=1,
                )

    for mapping in mappings:
        topic_id = str(mapping.get("topic", mapping.get("topic_id", mapping.get("id", ""))))
        topic_label = (
            mapping.get("topic_label")
            or mapping.get("label")
            or mapping.get("name")
            or f"Topic {topic_id}"
        )

        primary_domain = mapping.get("primary_domain") or mapping.get("domain") or "General"
        secondary_domain = mapping.get("secondary_domain")
        keywords = mapping.get("keywords", "")
        score = mapping.get("mapping_score", mapping.get("score", 1)) or 1

        topic_node_id = f"topic::{topic_id}"

        graph.add_node(
            topic_node_id,
            label=topic_label,
            title=(
                f"<b>{topic_label}</b><br>"
                f"Type: Topic<br>"
                f"Primary domain: {primary_domain}<br>"
                f"Candidates: {mapping.get('candidate_domain_labels', '')}<br>"
                f"Keywords: {keywords}"
            ),
            group="Topic",
            node_type="topic",
            domain=primary_domain,
            size=20 + min(float(score), 10),
            color="#f97316",
        )

        primary_domain_id = f"domain::{primary_domain}"
        if primary_domain_id in graph:
            graph.add_edge(
                topic_node_id,
                primary_domain_id,
                title="maps to primary domain",
                edge_type="primary_topic_domain",
                color="#f97316",
                width=4,
            )

        if secondary_domain:
            secondary_domain_id = f"domain::{secondary_domain}"
            if secondary_domain_id in graph:
                graph.add_edge(
                    topic_node_id,
                    secondary_domain_id,
                    title="maps to secondary domain",
                    edge_type="secondary_topic_domain",
                    color="#eab308",
                    width=2,
                    dashes=True,
                )

        if include_candidate_domain_edges:
            for candidate in mapping.get("candidate_domains", []) or []:
                if not isinstance(candidate, dict):
                    continue
                candidate_domain = candidate.get("domain")
                if not candidate_domain or candidate_domain in {primary_domain, secondary_domain}:
                    continue
                candidate_domain_id = f"domain::{candidate_domain}"
                if candidate_domain_id in graph:
                    graph.add_edge(
                        topic_node_id,
                        candidate_domain_id,
                        title=f"candidate domain score={candidate.get('score')}",
                        edge_type="candidate_topic_domain",
                        color="#fbbf24",
                        width=1,
                        dashes=True,
                    )

    return graph


def write_pyvis_semantic_graph(
    graph: nx.Graph,
    output_path: str | Path,
    *,
    height: str = "780px",
    width: str = "100%",
    notebook: bool = True,
    cdn_resources: str = "remote",
) -> Path:
    """Write an interactive 2D graph using PyVis.

    Requires optional dependencies:

        pip install pyvis networkx
    """
    try:
        from pyvis.network import Network
    except ImportError as exc:
        raise ImportError(
            "write_pyvis_semantic_graph requires pyvis. Install with: pip install pyvis"
        ) from exc

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    net = Network(
        height=height,
        width=width,
        bgcolor="#f8fafc",
        font_color="#0f172a",
        notebook=notebook,
        cdn_resources=cdn_resources,
    )

    net.from_nx(graph)

    net.set_options(
        """
{
  "nodes": {
    "borderWidth": 1,
    "borderWidthSelected": 3,
    "font": {
      "size": 16,
      "face": "Arial",
      "strokeWidth": 3,
      "strokeColor": "#ffffff"
    },
    "shape": "dot"
  },
  "edges": {
    "smooth": {
      "enabled": true,
      "type": "dynamic"
    },
    "font": {
      "size": 10,
      "align": "middle"
    }
  },
  "physics": {
    "enabled": true,
    "barnesHut": {
      "gravitationalConstant": -4200,
      "centralGravity": 0.25,
      "springLength": 130,
      "springConstant": 0.04,
      "damping": 0.18,
      "avoidOverlap": 0.55
    },
    "stabilization": {
      "enabled": true,
      "iterations": 600,
      "updateInterval": 25
    }
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 120,
    "navigationButtons": true,
    "keyboard": true,
    "multiselect": true
  },
  "manipulation": {
    "enabled": false
  }
}
"""
    )

    net.save_graph(str(output))
    return output


def display_html_graph(path: str | Path, *, width: str = "100%", height: int = 800):
    """Display a saved HTML graph in Jupyter when IPython is available."""
    try:
        from IPython.display import HTML, IFrame, display
    except ImportError as exc:
        raise ImportError("display_html_graph requires IPython/Jupyter") from exc

    graph_path = Path(path)
    if not graph_path.exists():
        display(HTML(f"<p style='color: #ef4444;'>Graph file not found: <code>{graph_path}</code></p>"))
        return

    # 1. Try IFrame with relative path (standard for classic Notebook/Lab)
    try:
        relative_path = os.path.relpath(graph_path, os.getcwd())
        display(IFrame(src=str(relative_path), width=width, height=height))
        return
    except Exception:
        pass

    # 2. Fallback: Read file and display as HTML object (robust for VS Code/restricted envs)
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        display(HTML(html_content))
        return
    except Exception:
        pass

    display(HTML(f"<p>Could not display graph inline. Open from Jupyter file browser: <code>{graph_path}</code></p>"))
