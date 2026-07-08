from __future__ import annotations

from .models import DownloadOptions


def duration_rejection_reason(info: dict, options: DownloadOptions) -> str | None:
    duration = info.get("duration")
    if duration is None:
        return None
    if options.min_duration is not None and duration < options.min_duration:
        return f"duration {duration}s is shorter than {options.min_duration}s"
    if options.max_duration is not None and duration > options.max_duration:
        return f"duration {duration}s is longer than {options.max_duration}s"
    return None


def make_match_filter(options: DownloadOptions):
    def _match_filter(info: dict, *, incomplete: bool = False) -> str | None:
        if incomplete:
            return None
        return duration_rejection_reason(info, options)

    return _match_filter
