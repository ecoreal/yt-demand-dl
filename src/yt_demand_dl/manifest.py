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
        if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or raw_limit < 1:
            raise ValueError(f"{path}:{line_number}: limit must be a positive integer")
        raw_query = item.get("query", False)
        if not isinstance(raw_query, bool):
            raise ValueError(f"{path}:{line_number}: query must be a boolean")
        raw_search_prefix = item.get("search_prefix", "ytsearch")
        if not isinstance(raw_search_prefix, str) or not raw_search_prefix.strip():
            raise ValueError(f"{path}:{line_number}: search_prefix must be a non-empty string")
        raw_label = item.get("label")
        if raw_label is not None and not isinstance(raw_label, str):
            raise ValueError(f"{path}:{line_number}: label must be a string")
        demands.append(
            VideoDemand(
                source=source.strip(),
                label=raw_label.strip() if raw_label and raw_label.strip() else None,
                query=raw_query,
                limit=raw_limit,
                search_prefix=raw_search_prefix.strip(),
                metadata={str(key): str(value) for key, value in metadata.items()},
            )
        )
    return demands
