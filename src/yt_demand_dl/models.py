from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Mapping


def validate_output_template(template: str) -> None:
    """Reject templates that can write outside the configured output directory."""

    if not isinstance(template, str) or not template.strip():
        raise ValueError("output_template must be a non-empty string")
    template_path = Path(template)
    portable_parts = PurePosixPath(template.replace("\\", "/")).parts
    windows_path = PureWindowsPath(template)
    if (
        template_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in template_path.parts
        or ".." in portable_parts
    ):
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
        if not isinstance(self.output_dir, Path):
            raise ValueError("output_dir must be a pathlib.Path")
        if not isinstance(self.format_selector, str) or not self.format_selector.strip():
            raise ValueError("format_selector must be a non-empty string")
        validate_output_template(self.output_template)
        _validate_optional_integer("max_duration", self.max_duration, minimum=1)
        _validate_optional_integer("min_duration", self.min_duration, minimum=0)
        if (
            self.min_duration is not None
            and self.max_duration is not None
            and self.min_duration > self.max_duration
        ):
            raise ValueError("min_duration must not exceed max_duration")
        if self.max_filesize is not None:
            _parse_filesize(self.max_filesize)
        _validate_optional_integer("retries", self.retries, minimum=0)
        _validate_optional_integer("fragment_retries", self.fragment_retries, minimum=0)
        if self.socket_timeout is not None:
            if (
                isinstance(self.socket_timeout, bool)
                or not isinstance(self.socket_timeout, (int, float))
                or not math.isfinite(self.socket_timeout)
                or self.socket_timeout <= 0
            ):
                raise ValueError("socket_timeout must be a finite number greater than 0")
        for name in (
            "dry_run",
            "write_info_json",
            "write_subtitles",
            "write_auto_subtitles",
            "no_playlist",
            "quiet",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")
        if not isinstance(self.subtitle_languages, (tuple, list)):
            raise ValueError("subtitle_languages must be a sequence of strings")
        if any(
            not isinstance(language, str) or not language.strip()
            for language in self.subtitle_languages
        ):
            raise ValueError("subtitle_languages must contain only non-empty strings")
        for name in ("download_archive", "cookies"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Path):
                raise ValueError(f"{name} must be a pathlib.Path")
        for name in ("cookies_from_browser", "proxy"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string")


def _validate_optional_integer(name: str, value: int | None, *, minimum: int) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise ValueError(f"{name} must be a {qualifier} integer")


_FILESIZE_RE = re.compile(
    r"^(?P<number>(?:\d+(?:\.\d*)?|\.\d+))\s*"
    r"(?P<unit>K|KB|M|MB|G|GB)?$",
    re.IGNORECASE,
)
_FILESIZE_MULTIPLIERS = {
    None: 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
}


def _parse_filesize(value: str) -> int:
    message = (
        "max_filesize must be a positive byte count, optionally suffixed with K/M/G"
    )
    if not isinstance(value, str):
        raise ValueError(message)
    match = _FILESIZE_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(message)
    try:
        amount = Decimal(match.group("number")) * _FILESIZE_MULTIPLIERS[
            match.group("unit").upper() if match.group("unit") else None
        ]
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError(message) from exc
    result = int(amount)
    if amount <= 0 or result < 1:
        raise ValueError(message)
    return result


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
