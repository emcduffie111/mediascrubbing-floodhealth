"""UCSD Map of Science full-backbone helpers.

This module adds an optional full UCSD Map of Science pull to the
semantic_bridge package. It fetches the public Pajek ``.net`` file used by the
Science Integrity Alliance science-map repository, caches it locally, parses the
vertex table, and converts it into the same rich science-backbone node shape
used by ``semantic_bridge.mapping.eto``.

Typical use from the Day 2 notebook:

    from semantic_bridge import api as sbp

    ucsd_layer = sbp.fetch_ucsd_science_backbone(
        cache_path=OUTPUT_DIR / "UCSDmap_with_disciplines.net.txt",
    )
    backbone_payload = sbp.build_science_backbone_payload(base_layer=ucsd_layer)

If the fetch or parse fails, use ``fallback_to_compact=True`` to return the
compact UCSD scaffold already bundled with the package.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any
import urllib.request

from semantic_bridge.mapping.eto import COMPACT_UCSD_SCAFFOLD

UCSD_NET_URL = (
    "https://raw.githubusercontent.com/Science-Integrity-Alliance/"
    "science-map/main/UCSDmap_with_disciplines.net.txt"
)

UCSD_DISCIPLINE_NAMES = {
    "Math & Physics",
    "Chemistry",
    "Earth Sciences",
    "Biology",
    "Biotechnology",
    "Infectious Disease",
    "Infectious Diseases",
    "Medical Specialties",
    "Health Professionals",
    "Brain Research",
    "Electrical Engineering & Computer Science",
    "Chemical, Mechanical, & Civil Engineering",
    "Social Sciences",
    "Humanities",
    # minor variants that appear in some copies of the file
    "Math and Physics",
    "Medical specialties",
    "Health professionals",
}

_VERTEX_RE = re.compile(
    r'^(\d+)\s+"([^"]+)"\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)'
    r'(?:\s+x_fact\s+([\d.eE+\-]+))?'
    r'(?:\s+y_fact\s+([\d.eE+\-]+))?'
    r'(?:\s+ic\s+(\S+))?'
    r'(?:\s+bc\s+(\S+))?'
)

_LABEL_STOPWORDS = {
    "the",
    "and",
    "of",
    "in",
    "on",
    "for",
    "to",
    "with",
    "by",
    "from",
    "an",
    "a",
    "or",
    "general",
    "other",
    "sciences",
    "science",
    "research",
    "studies",
}


def _canonical_discipline_name(label: str, scaffold: dict[str, Any]) -> str:
    """Normalize small spelling/case variants to scaffold labels."""
    label_key = label.lower().replace(" ", "").replace("&", "and")
    for discipline in scaffold:
        discipline_key = discipline.lower().replace(" ", "").replace("&", "and")
        if label_key == discipline_key:
            return discipline
    if label == "Infectious Disease" and "Infectious Diseases" in scaffold:
        return "Infectious Diseases"
    return label


def fetch_ucsd_net(
    url: str = UCSD_NET_URL,
    dest: str | Path = "outputs/UCSDmap_with_disciplines.net.txt",
    *,
    timeout: int = 30,
    min_size_bytes: int = 5_000,
    force: bool = False,
) -> Path:
    """Fetch and cache the UCSD Pajek ``.net`` source file.

    Parameters
    ----------
    url:
        Raw URL for the UCSD Map of Science Pajek file.
    dest:
        Local cache destination. Parent directories are created automatically.
    timeout:
        Network timeout in seconds.
    min_size_bytes:
        Existing files larger than this are treated as valid cache hits.
    force:
        If true, re-download even when a cache file exists.
    """
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if not force and dest_path.exists() and dest_path.stat().st_size > min_size_bytes:
        return dest_path

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "semantic-bridge-ucsd-backbone/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()

    if len(data) <= min_size_bytes:
        raise RuntimeError(
            f"Downloaded UCSD backbone file is unexpectedly small: {len(data)} bytes"
        )

    dest_path.write_bytes(data)
    return dest_path


def parse_ucsd_net(path: str | Path) -> list[dict[str, Any]]:
    """Parse the vertex section of a UCSD Map of Science Pajek ``.net`` file."""
    vertices: list[dict[str, Any]] = []
    section: str | None = None

    with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            lower = line.lower()
            if lower.startswith("*vertices"):
                section = "vertices"
                continue
            if lower.startswith("*edges") or lower.startswith("*arcs"):
                section = "edges"
                continue
            if section != "vertices":
                continue

            match = _VERTEX_RE.match(line)
            if not match:
                continue

            vertices.append(
                {
                    "id": int(match.group(1)),
                    "label": match.group(2),
                    "x": float(match.group(3)),
                    "y": float(match.group(4)),
                    "x_fact": float(match.group(5)) if match.group(5) else None,
                    "y_fact": float(match.group(6)) if match.group(6) else None,
                    "color": match.group(7) or "",
                    "border_color": match.group(8) or "",
                }
            )

    return vertices


def build_ucsd_full_backbone(
    vertices: list[dict[str, Any]],
    *,
    scaffold: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Build a rich UCSD backbone layer from parsed UCSD vertices.

    Returns
    -------
    tuple
        ``(backbone, stats)`` where ``backbone`` is compatible with
        ``build_science_backbone_payload(base_layer=...)`` and ``stats`` reports
        parsed/assigned/orphan counts.
    """
    scaffold_layer = deepcopy(scaffold or COMPACT_UCSD_SCAFFOLD)

    discipline_color: dict[str, str] = {}
    discipline_coords: dict[str, dict[str, float]] = {}

    for vertex in vertices:
        label = vertex["label"]
        if label in UCSD_DISCIPLINE_NAMES:
            canonical = _canonical_discipline_name(label, scaffold_layer)
            discipline_color[canonical] = vertex.get("color", "")
            discipline_coords[canonical] = {"x": vertex["x"], "y": vertex["y"]}

    if not discipline_color:
        raise RuntimeError(
            "No discipline anchor vertices were found in the UCSD .net file. "
            "The source format may have changed."
        )

    color_to_discipline = {color: discipline for discipline, color in discipline_color.items()}

    backbone: dict[str, dict[str, Any]] = {}
    for discipline, pajek_color in discipline_color.items():
        scaffold_node = scaffold_layer.get(discipline, {})
        backbone[discipline] = {
            "subdisciplines": [],
            "terms": list(scaffold_node.get("terms", [])),
            "color": scaffold_node.get("color") or pajek_color,
            "pajek_color": pajek_color,
            "coords": discipline_coords[discipline],
            "subdiscipline_coords": {},
            "source": "UCSD Map of Science full Pajek classification",
            "metadata": {
                "source_url": UCSD_NET_URL,
                "expected_vertices": "approximately 567 vertices: 554 subdisciplines + 13 disciplines",
            },
        }

    assigned = 0
    orphan = 0
    discipline_labels = {vertex["label"] for vertex in vertices if vertex["label"] in UCSD_DISCIPLINE_NAMES}

    for vertex in vertices:
        label = vertex["label"]
        if label in discipline_labels:
            continue

        parent = color_to_discipline.get(vertex.get("color", ""))
        if not parent:
            orphan += 1
            continue

        assigned += 1
        node = backbone[parent]
        node["subdisciplines"].append(label)
        node["subdiscipline_coords"][label] = {"x": vertex["x"], "y": vertex["y"]}

        existing_terms = set(node["terms"])
        for word in re.findall(r"[A-Za-z][A-Za-z\-]+", label.lower()):
            if len(word) > 2 and word not in _LABEL_STOPWORDS and word not in existing_terms:
                node["terms"].append(word)
                existing_terms.add(word)
        label_lower = label.lower()
        if label_lower not in existing_terms:
            node["terms"].append(label_lower)

    for node in backbone.values():
        node["subdisciplines"] = sorted(
            node["subdisciplines"],
            key=lambda value: value.lower(),
        )

    stats = {
        "n_vertices": len(vertices),
        "n_disciplines": len(backbone),
        "n_assigned_subdisciplines": assigned,
        "n_orphan_vertices": orphan,
    }
    return backbone, stats


def load_ucsd_science_backbone(
    net_path: str | Path,
    *,
    scaffold: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Parse a local UCSD Pajek file and return a rich science-backbone layer."""
    vertices = parse_ucsd_net(net_path)
    return build_ucsd_full_backbone(vertices, scaffold=scaffold)


def fetch_ucsd_science_backbone(
    *,
    url: str = UCSD_NET_URL,
    cache_path: str | Path = "outputs/UCSDmap_with_disciplines.net.txt",
    timeout: int = 30,
    force: bool = False,
    fallback_to_compact: bool = True,
    scaffold: dict[str, dict[str, Any]] | None = None,
    return_stats: bool = False,
) -> dict[str, dict[str, Any]] | tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Fetch, cache, parse, and return the full UCSD science-backbone layer.

    If ``fallback_to_compact`` is true, network or parse failures return the
    compact scaffold from ``semantic_bridge.mapping.eto`` with failure metadata.
    """
    try:
        net_path = fetch_ucsd_net(url, cache_path, timeout=timeout, force=force)
        backbone, stats = load_ucsd_science_backbone(net_path, scaffold=scaffold)
        stats["cache_path"] = str(net_path)
    except Exception as exc:
        if not fallback_to_compact:
            raise
        compact = deepcopy(scaffold or COMPACT_UCSD_SCAFFOLD)
        for node in compact.values():
            node.setdefault("source", "UCSD Map of Science compact scaffold fallback")
            metadata = dict(node.get("metadata", {}))
            metadata["ucsd_full_fetch_error"] = f"{type(exc).__name__}: {exc}"
            node["metadata"] = metadata
        stats = {
            "n_vertices": 0,
            "n_disciplines": len(compact),
            "n_assigned_subdisciplines": sum(
                len(node.get("subdisciplines", [])) for node in compact.values()
            ),
            "n_orphan_vertices": 0,
            "fallback": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
        backbone = compact

    return (backbone, stats) if return_stats else backbone


__all__ = [
    "UCSD_DISCIPLINE_NAMES",
    "UCSD_NET_URL",
    "build_ucsd_full_backbone",
    "fetch_ucsd_net",
    "fetch_ucsd_science_backbone",
    "load_ucsd_science_backbone",
    "parse_ucsd_net",
]
