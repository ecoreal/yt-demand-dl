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
    # Verification must only inspect files physically contained in the download
    # tree.  Following a directory or file symlink could make an unrelated
    # external file count as a completed download.
    if not directory.is_dir() or directory.is_symlink():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if not path.is_symlink()
        and path.is_file()
        and path.suffix.lower() in MEDIA_SUFFIXES
    )


def _archive_entries(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _selected_height(directory: Path) -> int | None:
    if not directory.is_dir() or directory.is_symlink():
        return None
    info_files = sorted(
        path
        for path in directory.iterdir()
        if not path.is_symlink() and path.is_file() and path.name.endswith(".info.json")
    )
    if not info_files:
        return None
    try:
        data = json.loads(info_files[0].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    # A truncated or hand-edited info JSON must not abort verification: only a
    # well-formed object is trusted, and a non-object root reports "unknown".
    if not isinstance(data, dict):
        return None
    requested = data.get("requested_downloads") or []
    if isinstance(requested, list):
        first = requested[0] if requested else None
        if isinstance(first, dict):
            height = first.get("height")
            if isinstance(height, int):
                return height
    height = data.get("height")
    return height if isinstance(height, int) else None
