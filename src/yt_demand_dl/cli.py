from __future__ import annotations

import argparse
import json
import os
import sys
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
from .models import DownloadOptions, VideoDemand
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-demand-dl",
        description="Demand-driven video downloads using yt-dlp as the engine.",
    )
    subparsers = parser.add_subparsers(required=True)

    list_parser = subparsers.add_parser("list-ap10k", help="List bundled AP-10K categories.")
    list_parser.add_argument("--limit", type=int, default=None)
    list_parser.set_defaults(func=_list_ap10k)

    download_parser = subparsers.add_parser("download", help="Download URLs or search queries.")
    _add_download_options(download_parser)
    download_parser.add_argument("sources", nargs="+")
    download_parser.add_argument("--label", default=None)
    download_parser.add_argument("--query", action="store_true", help="Treat sources as YouTube searches.")
    download_parser.add_argument("--limit", type=int, default=1, help="Search results per query.")
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
    ap10k_parser.add_argument("--category-limit", type=int, default=AP10K_DEFAULT_COUNT)
    ap10k_parser.add_argument("--videos-per-category", type=int, default=1)
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
    resume_parser.add_argument("--category-limit", type=int, default=AP10K_DEFAULT_COUNT)
    resume_parser.add_argument("--videos-per-category", type=int, default=1)
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
    verify_parser.add_argument("--category-limit", type=int, default=AP10K_DEFAULT_COUNT)
    verify_parser.add_argument("--archive", type=Path)
    verify_parser.add_argument(
        "--min-height",
        type=int,
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
        default="%(title).200B-%(id)s.%(ext)s",
        help="yt-dlp output template, placed under a label directory by default.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-duration", type=int)
    parser.add_argument("--min-duration", type=int)
    parser.add_argument("--max-filesize")
    parser.add_argument("--download-archive", type=Path)
    parser.add_argument(
        "--socket-timeout",
        type=float,
        help="Network socket timeout passed through to yt-dlp.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        help="HTTP retry count passed through to yt-dlp.",
    )
    parser.add_argument(
        "--fragment-retries",
        type=int,
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
        result = backend.download(job)
        print(f"  items={result.item_count} downloaded={result.downloaded}")
        if result.item_count == 0:
            failed += 1
    return 1 if failed else 0


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
        plan_output.parent.mkdir(parents=True, exist_ok=True)
        plan_output.write_text(
            "\n".join(json.dumps(line, ensure_ascii=True) for line in lines) + "\n",
            encoding="utf-8",
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
            args.missing_output.parent.mkdir(parents=True, exist_ok=True)
            args.missing_output.write_text(
                "\n".join(result.missing) + "\n",
                encoding="utf-8",
            )
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
        args.missing_output.parent.mkdir(parents=True, exist_ok=True)
        args.missing_output.write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
