from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .models import DownloadJob, DownloadOptions, VideoDemand

_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_label(label: str) -> str:
    cleaned = _SAFE_LABEL_RE.sub("_", label.strip().lower()).strip("_")
    return cleaned or "unlabeled"


def labelled_output_template(base_template: str, label: str) -> str:
    return str(Path(safe_label(label)) / base_template)


def build_jobs(
    demands: Iterable[VideoDemand],
    options: DownloadOptions,
    *,
    per_label_dirs: bool = True,
) -> list[DownloadJob]:
    jobs: list[DownloadJob] = []
    for demand in demands:
        job_options = options
        if per_label_dirs and demand.label:
            job_options = DownloadOptions(
                output_dir=options.output_dir,
                format_selector=options.format_selector,
                output_template=labelled_output_template(
                    options.output_template, demand.label
                ),
                dry_run=options.dry_run,
                max_duration=options.max_duration,
                min_duration=options.min_duration,
                max_filesize=options.max_filesize,
                write_info_json=options.write_info_json,
                write_subtitles=options.write_subtitles,
                write_auto_subtitles=options.write_auto_subtitles,
                subtitle_languages=options.subtitle_languages,
                download_archive=options.download_archive,
                cookies=options.cookies,
                cookies_from_browser=options.cookies_from_browser,
                proxy=options.proxy,
                socket_timeout=options.socket_timeout,
                retries=options.retries,
                fragment_retries=options.fragment_retries,
                no_playlist=options.no_playlist,
                quiet=options.quiet,
            )
        jobs.append(DownloadJob(demand=demand, options=job_options))
    return jobs
