# yt-demand-dl Project Summary

`yt-demand-dl` is a small Python library and CLI for demand-driven YouTube
video collection. It intentionally does not reimplement YouTube extraction,
signature handling, networking, or media downloading; those responsibilities are
delegated to `yt-dlp`.

## What It Provides

- Structured download requests via `VideoDemand` and `DownloadOptions`.
- A thin `YtDlpBackend` adapter over `yt-dlp`'s Python API.
- AP-10K category job generation for animal video collection.
- JSONL manifest downloads for explicit `label` to `source` mappings.
- Resume and verification commands for AP-10K collection runs.
- Pass-through support for cookies, browser cookies, proxy, timeout, retries,
  archive files, subtitles, and format selectors.
- Verification of category completeness and minimum selected video height.

## CLI Highlights

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k --plan-only --category-limit 53
PYTHONPATH=src python -m yt_demand_dl download-manifest examples/ap10k-missing-direct-urls.jsonl
PYTHONPATH=src python -m yt_demand_dl resume-ap10k data/ap10k-youtube
PYTHONPATH=src python -m yt_demand_dl verify-ap10k data/ap10k-youtube-hd --min-height 720
```

## Local Validation

The local workspace contains two completed AP-10K-style downloads:

- `data/ap10k-youtube`: 53 categories, low-bandwidth first pass.
- `data/ap10k-youtube-hd`: 53 categories, all selected videos at least 720p.

The media data is intentionally excluded from git because it is large generated
content and may be subject to source video licensing and platform terms.

Current local HD validation result:

- `complete=53/53 archive=53`
- 53 media files
- minimum selected height: 720p
- 48 videos at 1080p, 5 videos at 720p
