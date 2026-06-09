"""Shared type aliases for the semantic bridge package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

DocumentMap = dict[str, str]
DocumentPreview = dict[str, str]
TopicInfo = dict[str, Any]
TopicInfoMap = dict[str, TopicInfo]
TopicMapping = dict[str, Any]
DecisionComponent = dict[str, str]
DecisionComponents = dict[str, list[DecisionComponent]]
SVOMapping = dict[str, str]
OutputFiles = dict[str, Path]

