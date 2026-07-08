# yt-demand-dl

`yt-demand-dl` is a small Python library and CLI for demand-driven YouTube
downloads. It does not reimplement YouTube extraction or media downloading.
The actual engine is `yt-dlp`; this project adds a stable layer for describing
what you want to collect, turning category lists into search jobs, applying
simple constraints, and organizing outputs.

Use it only for videos you have the right to download and store, and follow
YouTube's terms and the source video's license.

## Install

```bash
python -m pip install -e ".[download]"
```

The package imports without `yt-dlp`, but real downloads require the optional
`download` extra.

## Quick examples

Dry-run one search:

```bash
PYTHONPATH=src python -m yt_demand_dl download "snow leopard animal video" \
  --query --limit 1 --dry-run
```

Download one URL:

```bash
yt-demand-dl download "https://www.youtube.com/watch?v=VIDEO_ID" \
  --label snow-leopard --output data/videos
```

Download a JSONL manifest:

```bash
PYTHONPATH=src python -m yt_demand_dl download-manifest examples/ap10k-missing-direct-urls.jsonl \
  --output data/ap10k-youtube \
  --download-archive data/ap10k-youtube/archive.txt \
  --proxy http://127.0.0.1:2266
```

List AP-10K categories:

```bash
PYTHONPATH=src python -m yt_demand_dl list-ap10k --limit 53
```

Create a 53-category AP-10K download plan without importing `yt-dlp` or touching
the network:

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k \
  --category-limit 53 \
  --plan-output data/ap10k-youtube/plan.jsonl
```

Download one YouTube search result for each of 53 AP-10K categories:

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k \
  --category-limit 53 \
  --videos-per-category 1 \
  --output data/ap10k-youtube \
  --format "worst[vcodec!=none][acodec!=none]/worst" \
  --max-duration 180 \
  --max-filesize 20M \
  --download-archive data/ap10k-youtube/archive.txt
```

If YouTube requires login verification in your environment, pass cookies through
to `yt-dlp` rather than implementing any extraction logic here:

```bash
YT_DEMAND_DL_COOKIES=/path/to/www.youtube.com_cookies.txt \
PYTHONPATH=src python -m yt_demand_dl ap10k --category-limit 53
```

AP-10K is documented by the official project and paper as 23 families and
54 species. The command defaults to 53 categories because that is the requested
collection target here. To use all bundled categories:

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k --category-limit 54
```

To use a category list extracted from your AP-10K annotations:

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k \
  --categories-file path/to/ap10k_annotations.json \
  --category-limit 53
```

COCO-style `categories[].name`, JSON string arrays, and newline-separated text
files are supported.

## Python API

```python
from pathlib import Path

from yt_demand_dl.ap10k import make_ap10k_jobs
from yt_demand_dl.backends import YtDlpBackend
from yt_demand_dl.models import DownloadOptions
from yt_demand_dl.planner import build_jobs

demands = make_ap10k_jobs(category_limit=53, videos_per_category=1)
options = DownloadOptions(
    output_dir=Path("data/ap10k-youtube"),
    format_selector="worst[vcodec!=none][acodec!=none]/worst",
    max_duration=180,
    max_filesize="20M",
)

backend = YtDlpBackend()
for job in build_jobs(demands, options):
    backend.download(job)
```

## Tests

Offline tests use only the standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Real YouTube integration test:

```bash
YT_DEMAND_DL_RUN_NETWORK=1 PYTHONPATH=src \
  python -m unittest tests.test_integration_youtube
```

That test downloads one result for each of 53 AP-10K categories. It requires
`yt-dlp`, network access, and enough disk space for the selected format.

Verify a completed AP-10K download directory:

```bash
PYTHONPATH=src python -m yt_demand_dl verify-ap10k data/ap10k-youtube
```

Require downloaded `yt-dlp` metadata to show at least 720p:

```bash
PYTHONPATH=src python -m yt_demand_dl verify-ap10k data/ap10k-youtube-hd --min-height 720
```

Resume only missing categories:

```bash
PYTHONPATH=src python -m yt_demand_dl verify-ap10k data/ap10k-youtube \
  --missing-output /tmp/ap10k-missing.txt

YT_DEMAND_DL_COOKIES=/path/to/www.youtube.com_cookies.txt \
PYTHONPATH=src python -m yt_demand_dl ap10k \
  --categories-file /tmp/ap10k-missing.txt \
  --category-limit 999 \
  --query-template "{category} animal facts for kids" \
  --output data/ap10k-youtube \
  --download-archive data/ap10k-youtube/archive.txt \
  --socket-timeout 15 \
  --retries 3 \
  --fragment-retries 3
```

Or let the CLI do the verify-and-resume step:

```bash
YT_DEMAND_DL_COOKIES=/path/to/www.youtube.com_cookies.txt \
PYTHONPATH=src python -m yt_demand_dl resume-ap10k data/ap10k-youtube \
  --download-archive data/ap10k-youtube/archive.txt \
  --proxy http://127.0.0.1:2266
```
