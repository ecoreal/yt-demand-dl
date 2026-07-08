from __future__ import annotations

from pathlib import Path
from typing import Any

from yt_demand_dl.filters import make_match_filter
from yt_demand_dl.models import DownloadJob, DownloadOptions, DownloadResult


class MissingYtDlpError(RuntimeError):
    pass


class YtDlpBackend:
    """Thin adapter around yt-dlp's Python API."""

    def __init__(self, youtube_dl_cls: type | None = None) -> None:
        self._youtube_dl_cls = youtube_dl_cls

    @staticmethod
    def available() -> bool:
        try:
            import yt_dlp  # noqa: F401
        except ModuleNotFoundError:
            return False
        return True

    def build_options(self, options: DownloadOptions) -> dict[str, Any]:
        ydl_options: dict[str, Any] = {
            "format": options.format_selector,
            "outtmpl": str(options.output_dir / options.output_template),
            "noplaylist": options.no_playlist,
            "quiet": options.quiet,
            "noprogress": options.quiet,
            "ignoreerrors": True,
            "restrictfilenames": True,
            "writeinfojson": options.write_info_json,
            "writesubtitles": options.write_subtitles,
            "writeautomaticsub": options.write_auto_subtitles,
            "subtitleslangs": list(options.subtitle_languages),
            "match_filter": make_match_filter(options),
        }
        if options.dry_run:
            ydl_options.update({"simulate": True, "skip_download": True})
        if options.max_filesize:
            ydl_options["max_filesize"] = _parse_filesize(options.max_filesize)
        if options.download_archive:
            ydl_options["download_archive"] = str(options.download_archive)
        if options.cookies:
            ydl_options["cookiefile"] = str(options.cookies)
        if options.cookies_from_browser:
            ydl_options["cookiesfrombrowser"] = _parse_cookies_from_browser(
                options.cookies_from_browser
            )
        if options.proxy:
            ydl_options["proxy"] = options.proxy
        if options.socket_timeout is not None:
            ydl_options["socket_timeout"] = options.socket_timeout
        if options.retries is not None:
            ydl_options["retries"] = options.retries
        if options.fragment_retries is not None:
            ydl_options["fragment_retries"] = options.fragment_retries
        return ydl_options

    def download(self, job: DownloadJob) -> DownloadResult:
        job.options.output_dir.mkdir(parents=True, exist_ok=True)
        youtube_dl_cls = self._resolve_youtube_dl_cls()
        ydl_options = self.build_options(job.options)
        downloaded_files: list[Path] = []
        if not job.options.dry_run:
            ydl_options.setdefault("progress_hooks", []).append(
                _download_progress_hook(downloaded_files)
            )
        source = job.demand.resolved_source()
        with youtube_dl_cls(ydl_options) as ydl:
            info = ydl.extract_info(source, download=not job.options.dry_run)
        ids = tuple(_extract_ids(info))
        files = tuple(_existing_media_files(job)) or tuple(downloaded_files)
        item_count = len(ids) if job.options.dry_run else len(files)
        return DownloadResult(
            source=source,
            label=job.label,
            downloaded=not job.options.dry_run,
            item_count=item_count,
            ids=ids,
            files=files,
        )

    def _resolve_youtube_dl_cls(self):
        if self._youtube_dl_cls is not None:
            return self._youtube_dl_cls
        try:
            from yt_dlp import YoutubeDL
        except ModuleNotFoundError as exc:
            raise MissingYtDlpError(
                "yt-dlp is not installed. Install with: "
                "python -m pip install 'yt-demand-dl[download]'"
            ) from exc
        return YoutubeDL


def _extract_ids(info: Any) -> list[str]:
    if not info:
        return []
    if isinstance(info, dict) and "entries" in info:
        ids: list[str] = []
        for entry in info.get("entries") or []:
            ids.extend(_extract_ids(entry))
        return ids
    if isinstance(info, dict):
        video_id = info.get("id")
        return [str(video_id)] if video_id else []
    return []


def _parse_cookies_from_browser(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.split(":") if part)


def _parse_filesize(value: str) -> int:
    text = value.strip().upper()
    units = {
        "K": 1024,
        "KB": 1024,
        "M": 1024**2,
        "MB": 1024**2,
        "G": 1024**3,
        "GB": 1024**3,
    }
    for suffix, multiplier in sorted(units.items(), key=lambda item: len(item[0]), reverse=True):
        if text.endswith(suffix):
            return int(float(text[: -len(suffix)].strip()) * multiplier)
    return int(text)


def _download_progress_hook(downloaded_files: list[Path]):
    def _hook(status: dict[str, Any]) -> None:
        if status.get("status") != "finished":
            return
        filename = status.get("filename")
        if filename:
            downloaded_files.append(Path(filename))

    return _hook


def _existing_media_files(job: DownloadJob) -> list[Path]:
    output_path = job.options.output_dir / job.options.output_template
    directory = output_path.parent
    if not directory.exists():
        return []
    media_suffixes = {".mp4", ".webm", ".mkv", ".mov", ".m4v"}
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in media_suffixes
    )
