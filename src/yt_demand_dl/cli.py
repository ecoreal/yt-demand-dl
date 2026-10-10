from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

from .ap10k import (
    AP10K_CATEGORIES,
    AP10K_DEFAULT_COUNT,
    load_categories,
    make_ap10k_jobs,
    select_categories,
)
from .backends import MissingYtDlpError, YtDlpBackend
from .manifest import load_manifest
from .models import DownloadOptions, VideoDemand, validate_output_template
from .planner import build_jobs
from .verify import verify_ap10k_downloads


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MissingYtDlpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return parsed


def _max_filesize(value: str) -> str:
    text = value.strip().upper()
    units = {"K": 1024, "KB": 1024, "M": 1024**2, "MB": 1024**2, "G": 1024**3, "GB": 1024**3}
    multiplier = 1
    number = text
    for suffix, candidate in sorted(units.items(), key=lambda item: len(item[0]), reverse=True):
        if text.endswith(suffix):
            multiplier = candidate
            number = text[:-len(suffix)].strip()
            break
    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", number):
        raise argparse.ArgumentTypeError("must be a positive byte count, optionally suffixed with K/M/G")
    try:
        amount = float(number)
        byte_count = amount * multiplier
    except (OverflowError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a positive byte count, optionally suffixed with K/M/G") from exc
    if not math.isfinite(byte_count) or byte_count < 1:
        raise argparse.ArgumentTypeError("must be a positive byte count, optionally suffixed with K/M/G")
    return value


def _output_template(value: str) -> str:
    try:
        validate_output_template(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-demand-dl",
        description="Demand-driven video downloads using yt-dlp as the engine.",
    )
    subparsers = parser.add_subparsers(required=True)

    list_parser = subparsers.add_parser("list-ap10k", help="List bundled AP-10K categories.")
    list_parser.add_argument("--limit", type=_positive_int, default=None)
    list_parser.set_defaults(func=_list_ap10k)

    download_parser = subparsers.add_parser("download", help="Download URLs or search queries.")
    _add_download_options(download_parser)
    download_parser.add_argument("sources", nargs="+")
    download_parser.add_argument("--label", default=None)
    download_parser.add_argument("--query", action="store_true", help="Treat sources as YouTube searches.")
    download_parser.add_argument("--limit", type=_positive_int, default=1, help="Search results per query.")
    download_parser.set_defaults(func=_download_sources)

    manifest_parser = subparsers.add_parser(
        "download-manifest",
        help="Download jobs from a JSONL manifest with label/source fields.",
    )
    _add_download_options(manifest_parser)
    manifest_parser.add_argument("manifest", type=Path)
    manifest_parser.set_defaults(func=_download_manifest)

    ap10k_parser = subparsers.add_parser(
        "ap10k",
        help="Download one or more YouTube videos for AP-10K animal categories.",
    )
    _add_download_options(ap10k_parser)
    ap10k_parser.add_argument("--categories-file", type=Path)
    ap10k_parser.add_argument("--category-limit", type=_positive_int, default=AP10K_DEFAULT_COUNT)
    ap10k_parser.add_argument("--videos-per-category", type=_positive_int, default=1)
    ap10k_parser.add_argument(
        "--query-template",
        default="{category} animal video",
        help="Python format string with {category}.",
    )
    ap10k_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Category name to exclude. Can be repeated.",
    )
    ap10k_parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print AP-10K jobs without importing yt-dlp or touching the network.",
    )
    ap10k_parser.add_argument(
        "--plan-output",
        type=Path,
        help="Write the AP-10K plan as JSONL. Implies --plan-only.",
    )
    ap10k_parser.set_defaults(func=_download_ap10k)

    resume_parser = subparsers.add_parser(
        "resume-ap10k",
        help="Verify an AP-10K download directory and download only missing categories.",
    )
    resume_parser.add_argument("root", type=Path)
    _add_download_options(resume_parser, output_default=None)
    resume_parser.add_argument("--category-limit", type=_positive_int, default=AP10K_DEFAULT_COUNT)
    resume_parser.add_argument("--videos-per-category", type=_positive_int, default=1)
    resume_parser.add_argument(
        "--query-template",
        default="{category} animal facts for kids",
        help="Python format string with {category}.",
    )
    resume_parser.set_defaults(func=_resume_ap10k)

    verify_parser = subparsers.add_parser(
        "verify-ap10k",
        help="Verify that each AP-10K category directory contains a media file.",
    )
    verify_parser.add_argument("root", type=Path)
    verify_parser.add_argument("--category-limit", type=_positive_int, default=AP10K_DEFAULT_COUNT)
    verify_parser.add_argument("--archive", type=Path)
    verify_parser.add_argument(
        "--min-height",
        type=_non_negative_int,
        help="Require selected yt-dlp info JSON height to be at least this value.",
    )
    verify_parser.add_argument(
        "--missing-output",
        type=Path,
        help="Write missing category names as newline-separated text.",
    )
    verify_parser.set_defaults(func=_verify_ap10k)
    return parser


def _add_download_options(
    parser: argparse.ArgumentParser,
    *,
    output_default: Path | None = Path("downloads"),
) -> None:
    parser.add_argument("--output", type=Path, default=output_default)
    parser.add_argument(
        "--format",
        dest="format_selector",
        default=(
            "best[height<=720][vcodec!=none][acodec!=none]/"
            "best[vcodec!=none][acodec!=none]/best"
        ),
    )
    parser.add_argument(
        "--output-template",
        type=_output_template,
        default="%(title).200B-%(id)s.%(ext)s",
        help=(
            "yt-dlp output template; use a relative path without '..' components "
            "and place it under a label directory by default."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-duration", type=_positive_int)
    parser.add_argument("--min-duration", type=_non_negative_int)
    parser.add_argument("--max-filesize", type=_max_filesize)
    parser.add_argument("--download-archive", type=Path)
    parser.add_argument(
        "--socket-timeout",
        type=_positive_float,
        help="Network socket timeout passed through to yt-dlp.",
    )
    parser.add_argument(
        "--retries",
        type=_non_negative_int,
        help="HTTP retry count passed through to yt-dlp.",
    )
    parser.add_argument(
        "--fragment-retries",
        type=_non_negative_int,
        help="Fragment retry count passed through to yt-dlp.",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=Path(os.environ["YT_DEMAND_DL_COOKIES"])
        if os.environ.get("YT_DEMAND_DL_COOKIES")
        else None,
        help="Netscape cookies.txt file passed through to yt-dlp.",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=os.environ.get("YT_DEMAND_DL_COOKIES_FROM_BROWSER"),
        help="Browser spec passed through to yt-dlp, e.g. chrome or firefox:profile.",
    )
    parser.add_argument(
        "--proxy",
        default=os.environ.get("YT_DEMAND_DL_PROXY"),
        help="Proxy URL passed through to yt-dlp, e.g. http://127.0.0.1:2266.",
    )
    parser.add_argument("--no-info-json", action="store_true")
    parser.add_argument("--subtitles", action="store_true")
    parser.add_argument("--auto-subtitles", action="store_true")
    parser.add_argument("--subtitle-language", action="append", default=[])
    parser.add_argument("--quiet", action="store_true")


def _download_options_from_args(args: argparse.Namespace) -> DownloadOptions:
    return DownloadOptions(
        output_dir=args.output or Path("downloads"),
        format_selector=args.format_selector,
        output_template=args.output_template,
        dry_run=args.dry_run,
        max_duration=args.max_duration,
        min_duration=args.min_duration,
        max_filesize=args.max_filesize,
        write_info_json=not args.no_info_json,
        write_subtitles=args.subtitles,
        write_auto_subtitles=args.auto_subtitles,
        subtitle_languages=tuple(args.subtitle_language or ["en"]),
        download_archive=args.download_archive,
        cookies=args.cookies,
        cookies_from_browser=args.cookies_from_browser,
        proxy=args.proxy,
        socket_timeout=args.socket_timeout,
        retries=args.retries,
        fragment_retries=args.fragment_retries,
        quiet=args.quiet,
    )


def _list_ap10k(args: argparse.Namespace) -> int:
    categories = select_categories(AP10K_CATEGORIES, limit=args.limit)
    for category in categories:
        print(category)
    return 0


def _download_sources(args: argparse.Namespace) -> int:
    options = _download_options_from_args(args)
    demands = [
        VideoDemand(
            source=source,
            label=args.label or ("search" if args.query else "url"),
            query=args.query,
            limit=args.limit,
        )
        for source in args.sources
    ]
    return _run_jobs(build_jobs(demands, options))


def _download_manifest(args: argparse.Namespace) -> int:
    return _run_jobs(build_jobs(load_manifest(args.manifest), _download_options_from_args(args)))


def _download_ap10k(args: argparse.Namespace) -> int:
    categories = AP10K_CATEGORIES
    if args.categories_file:
        categories = load_categories(args.categories_file)
    demands = make_ap10k_jobs(
        categories=categories,
        category_limit=args.category_limit,
        videos_per_category=args.videos_per_category,
        query_template=args.query_template,
        exclude=args.exclude,
    )
    jobs = build_jobs(demands, _download_options_from_args(args))
    if args.plan_only or args.plan_output:
        return _print_plan(jobs, args.plan_output)
    return _run_jobs(jobs)


def _resume_ap10k(args: argparse.Namespace) -> int:
    verification = verify_ap10k_downloads(args.root, category_limit=args.category_limit)
    if not verification.missing:
        print(f"complete={verification.complete_count}/{verification.expected_count}")
        return 0
    print(
        f"complete={verification.complete_count}/{verification.expected_count}; "
        f"resuming {len(verification.missing)} missing categories"
    )
    args.output = args.output or args.root
    demands = make_ap10k_jobs(
        categories=verification.missing,
        category_limit=None,
        videos_per_category=args.videos_per_category,
        query_template=args.query_template,
    )
    return _run_jobs(build_jobs(demands, _download_options_from_args(args)))


def _run_jobs(jobs) -> int:
    backend = YtDlpBackend()
    failed = 0
    for job in jobs:
        print(f"{job.label}: {job.demand.resolved_source()}")
        try:
            result = backend.download(job)
        except MissingYtDlpError:
            raise
        except Exception as exc:
            failed += 1
            message = str(exc) or exc.__class__.__name__
            print(f"  error={message}", file=sys.stderr)
            continue
        print(f"  items={result.item_count} downloaded={result.downloaded}")
        if result.item_count == 0:
            failed += 1
    return 1 if failed else 0


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _print_plan(jobs, plan_output: Path | None = None) -> int:
    lines = [
        {
            "label": job.label,
            "source": job.demand.resolved_source(),
            "output_template": str(job.options.output_dir / job.options.output_template),
        }
        for job in jobs
    ]
    if plan_output:
        _atomic_write_text(
            plan_output,
            "\n".join(json.dumps(line, ensure_ascii=True) for line in lines) + "\n",
        )
    for line in lines:
        print(f"{line['label']}: {line['source']}")
    return 0


def _verify_ap10k(args: argparse.Namespace) -> int:
    result = verify_ap10k_downloads(
        args.root,
        category_limit=args.category_limit,
        archive=args.archive,
    )
    print(
        f"complete={result.complete_count}/{result.expected_count} "
        f"archive={result.archive_entries if result.archive_entries is not None else 'missing'}"
    )
    if result.missing:
        print("missing:")
        for category in result.missing:
            print(f"  {category}")
        if args.missing_output:
            _atomic_write_text(args.missing_output, "\n".join(result.missing) + "\n")
        return 1
    if args.min_height is not None:
        below = result.below_min_height(args.min_height)
        if below:
            print(f"below_min_height={args.min_height}:")
            for status in below:
                height = status.selected_height if status.selected_height is not None else "unknown"
                print(f"  {status.category}: {height}")
            return 1
    if args.missing_output:
        _atomic_write_text(args.missing_output, "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
