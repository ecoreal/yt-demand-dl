from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .ap10k import make_ap10k_jobs
from .planner import safe_label

MEDIA_SUFFIXES = frozenset({".mp4", ".webm", ".mkv", ".mov", ".m4v"})


@dataclass(frozen=True)
class CategoryStatus:
    category: str
    directory: Path
    files: tuple[Path, ...]
    selected_height: int | None = None

    @property
    def complete(self) -> bool:
        return bool(self.files)


@dataclass(frozen=True)
class Ap10kVerification:
    root: Path
    statuses: tuple[CategoryStatus, ...]
    archive_entries: int | None

    @property
    def complete_count(self) -> int:
        return sum(1 for status in self.statuses if status.complete)

    @property
    def expected_count(self) -> int:
        return len(self.statuses)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(status.category for status in self.statuses if not status.complete)

    @property
    def complete(self) -> bool:
        return self.complete_count == self.expected_count

    def below_min_height(self, min_height: int) -> tuple[CategoryStatus, ...]:
        return tuple(
            status
            for status in self.statuses
            if status.selected_height is None or status.selected_height < min_height
        )


def verify_ap10k_downloads(
    root: Path,
    *,
    category_limit: int = 53,
    archive: Path | None = None,
) -> Ap10kVerification:
    statuses: list[CategoryStatus] = []
    for demand in make_ap10k_jobs(category_limit=category_limit):
        category = demand.label or ""
        directory = root / safe_label(category)
        files = tuple(_media_files(directory))
        statuses.append(
            CategoryStatus(
                category=category,
                directory=directory,
                files=files,
                selected_height=_selected_height(directory),
            )
        )
    archive_entries = _archive_entries(archive or root / "archive.txt")
    return Ap10kVerification(
        root=root,
        statuses=tuple(statuses),
        archive_entries=archive_entries,
    )


def _media_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES
    )


def _archive_entries(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _selected_height(directory: Path) -> int | None:
    if not directory.exists():
        return None
    info_files = sorted(directory.glob("*.info.json"))
    if not info_files:
        return None
    try:
        data = json.loads(info_files[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    requested = data.get("requested_downloads") or []
    if requested and isinstance(requested[0], dict):
        height = requested[0].get("height")
        if isinstance(height, int):
            return height
    height = data.get("height")
    return height if isinstance(height, int) else None
