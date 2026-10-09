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
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        source = item.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"{path}:{line_number}: source must be a non-empty string")
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"{path}:{line_number}: metadata must be an object")
        raw_limit = item.get("limit", 1)
        if isinstance(raw_limit, bool):
            raise ValueError(f"{path}:{line_number}: limit must be a positive integer")
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{line_number}: limit must be a positive integer") from exc
        if limit < 1:
            raise ValueError(f"{path}:{line_number}: limit must be a positive integer")
        search_prefix = str(item.get("search_prefix", "ytsearch")).strip()
        if not search_prefix:
            raise ValueError(f"{path}:{line_number}: search_prefix must not be empty")
        demands.append(
            VideoDemand(
                source=source.strip(),
                label=str(item["label"]).strip() if item.get("label") else None,
                query=bool(item.get("query", False)),
                limit=limit,
                search_prefix=search_prefix,
                metadata={str(key): str(value) for key, value in metadata.items()},
            )
        )
    return demands
