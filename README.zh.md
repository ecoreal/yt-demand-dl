# yt-demand-dl

[![CI](https://github.com/ecoreal/yt-demand-dl/actions/workflows/ci.yml/badge.svg)](https://github.com/ecoreal/yt-demand-dl/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](README.md) · 中文

`yt-demand-dl` 是一个轻量的 Python 库和 CLI，面向「按需求驱动」的 YouTube
下载。它不重新实现 YouTube 提取或媒体下载——真正的引擎是 `yt-dlp`；本项目
在其上提供稳定的一层：描述你想收集什么、把类别清单转成搜索任务、应用简单
约束、并组织输出。

- **类别计划生成器**：一条命令把 AP-10K 类别（或你自己的清单）转成搜索任务；
  `--plan-output` 模式完全不联网，适合 dry-run 与 CI。
- **清单驱动批量下载**：用 JSONL 描述下载；planner 在任何网络请求之前校验
  每一行（大小上限、相对输出模板）。
- **内建断点续传**：`verify-ap10k` 审计缺了什么，`resume-ap10k` 精确重排
  这些类别。
- **刻意保持对 yt-dlp 的薄封装**：提取、格式与 cookie 都留在 yt-dlp，两者
  独立演进。

请仅下载你有权保存的内容，并遵守 YouTube 条款与源视频的许可。

## 安装

```bash
python -m pip install -e ".[download]"
```

包本身不装 `yt-dlp` 也能导入；真实下载需要可选的 `download` extra。

## 快速示例

Dry-run 一次搜索：

```bash
PYTHONPATH=src python -m yt_demand_dl download "snow leopard animal video" \
  --query --limit 1 --dry-run
```

下载单个 URL：

```bash
yt-demand-dl download "https://www.youtube.com/watch?v=VIDEO_ID" \
  --label snow-leopard --output data/videos
```

下载 JSONL 清单：

```bash
PYTHONPATH=src python -m yt_demand_dl download-manifest examples/ap10k-missing-direct-urls.jsonl \
  --output data/ap10k-youtube \
  --download-archive data/ap10k-youtube/archive.txt \
  --proxy http://127.0.0.1:2266
```

列出 AP-10K 类别：

```bash
PYTHONPATH=src python -m yt_demand_dl list-ap10k --limit 53
```

生成 53 类 AP-10K 下载计划（不导入 `yt-dlp`、不触网）：

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k \
  --category-limit 53 \
  --plan-output data/ap10k-youtube/plan.jsonl
```

为 53 个 AP-10K 类别各下载一个 YouTube 搜索结果：

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

如果所在环境触发 YouTube 登录验证，请把 cookie 透传给 `yt-dlp`，而不是在本
项目里实现任何提取逻辑：

```bash
YT_DEMAND_DL_COOKIES=/path/to/www.youtube.com_cookies.txt \
PYTHONPATH=src python -m yt_demand_dl ap10k --category-limit 53
```

AP-10K 官方项目与论文记录为 23 个科、54 个物种。本命令默认 53 类，因为这是
这里设定的收集目标。要使用全部内置类别：

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k --category-limit 54
```

使用从你的 AP-10K 标注中提取的类别清单：

```bash
PYTHONPATH=src python -m yt_demand_dl ap10k \
  --categories-file path/to/ap10k_annotations.json \
  --category-limit 53
```

支持 COCO 风格 `categories[].name`、JSON 字符串数组，以及按行分隔的文本文件。

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

## 测试

离线测试只用标准库：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

真实 YouTube 集成测试：

```bash
YT_DEMAND_DL_RUN_NETWORK=1 PYTHONPATH=src \
  python -m unittest tests.test_integration_youtube
```

该测试会为 53 个 AP-10K 类别各下载一个结果，需要 `yt-dlp`、网络访问，以及
足够的磁盘空间。

校验已完成的 AP-10K 下载目录：

```bash
PYTHONPATH=src python -m yt_demand_dl verify-ap10k data/ap10k-youtube
```

要求已下载的 `yt-dlp` 元数据至少为 720p：

```bash
PYTHONPATH=src python -m yt_demand_dl verify-ap10k data/ap10k-youtube-hd --min-height 720
```

只续传缺失的类别：

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

或者让 CLI 一步完成「校验并续传」：

```bash
YT_DEMAND_DL_COOKIES=/path/to/www.youtube.com_cookies.txt \
PYTHONPATH=src python -m yt_demand_dl resume-ap10k data/ap10k-youtube \
  --download-archive data/ap10k-youtube/archive.txt \
  --proxy http://127.0.0.1:2266
```

CI 在受支持的 Python 版本上运行离线 unittest 套件和无网络的 AP-10K 计划
冒烟测试。开发环境见 [CONTRIBUTING.md](CONTRIBUTING.md)，漏洞私密报告见
[SECURITY.md](SECURITY.md)，PyPI 发布流程见
[docs/releasing.md](docs/releasing.md)，版本历史见
[CHANGELOG.md](CHANGELOG.md)。
