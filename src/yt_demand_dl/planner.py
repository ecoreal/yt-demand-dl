from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
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
            job_options = replace(
                options,
                output_template=labelled_output_template(
                    options.output_template, demand.label
                ),
            )
        jobs.append(DownloadJob(demand=demand, options=job_options))
    return jobs
