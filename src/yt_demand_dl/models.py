from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


def validate_output_template(template: str) -> None:
    """Reject templates that can write outside the configured output directory."""

    if not isinstance(template, str) or not template.strip():
        raise ValueError("output_template must be a non-empty string")
    template_path = Path(template)
    if template_path.is_absolute() or ".." in template_path.parts:
        raise ValueError(
            "output_template must be a relative path without '..' components"
        )


@dataclass(frozen=True)
class VideoDemand:
    """The user's intent for one video source or search query."""

    source: str
    label: str | None = None
    query: bool = False
    limit: int = 1
    search_prefix: str = "ytsearch"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def resolved_source(self) -> str:
        if not self.query:
            return self.source
        return f"{self.search_prefix}{self.limit}:{self.source}"


@dataclass(frozen=True)
class DownloadOptions:
    """Options that map directly to stable yt-dlp concepts."""

    output_dir: Path = Path("downloads")
    format_selector: str = (
        "best[height<=720][vcodec!=none][acodec!=none]/"
        "best[vcodec!=none][acodec!=none]/best"
    )
    output_template: str = "%(title).200B-%(id)s.%(ext)s"
    dry_run: bool = False
    max_duration: int | None = None
    min_duration: int | None = None
    max_filesize: str | None = None
    write_info_json: bool = True
    write_subtitles: bool = False
    write_auto_subtitles: bool = False
    subtitle_languages: tuple[str, ...] = ("en",)
    download_archive: Path | None = None
    cookies: Path | None = None
    cookies_from_browser: str | None = None
    proxy: str | None = None
    socket_timeout: float | None = None
    retries: int | None = None
    fragment_retries: int | None = None
    no_playlist: bool = True
    quiet: bool = False

    def __post_init__(self) -> None:
        validate_output_template(self.output_template)


@dataclass(frozen=True)
class DownloadJob:
    demand: VideoDemand
    options: DownloadOptions

    @property
    def label(self) -> str:
        return self.demand.label or "unlabeled"


@dataclass(frozen=True)
class DownloadResult:
    source: str
    label: str
    downloaded: bool
    item_count: int
    ids: tuple[str, ...] = ()
    files: tuple[Path, ...] = ()
