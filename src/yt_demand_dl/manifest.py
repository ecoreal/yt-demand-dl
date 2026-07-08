from __future__ import annotations

import json
from pathlib import Path

from .models import VideoDemand


def load_manifest(path: Path) -> list[VideoDemand]:
    demands: list[VideoDemand] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        item = json.loads(stripped)
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        source = item.get("source")
        if not source:
            raise ValueError(f"{path}:{line_number}: missing source")
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"{path}:{line_number}: metadata must be an object")
        demands.append(
            VideoDemand(
                source=str(source),
                label=str(item["label"]) if item.get("label") else None,
                query=bool(item.get("query", False)),
                limit=int(item.get("limit", 1)),
                search_prefix=str(item.get("search_prefix", "ytsearch")),
                metadata={str(key): str(value) for key, value in metadata.items()},
            )
        )
    return demands
