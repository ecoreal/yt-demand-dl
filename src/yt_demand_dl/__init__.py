"""Demand-driven downloader helpers built on top of yt-dlp."""

from .ap10k import AP10K_CATEGORIES, AP10K_DEFAULT_COUNT, make_ap10k_jobs
from .manifest import load_manifest
from .models import DownloadJob, DownloadOptions, DownloadResult, VideoDemand
from .planner import build_jobs
from .verify import Ap10kVerification, CategoryStatus, verify_ap10k_downloads

__all__ = [
    "AP10K_CATEGORIES",
    "AP10K_DEFAULT_COUNT",
    "DownloadJob",
    "DownloadOptions",
    "DownloadResult",
    "VideoDemand",
    "Ap10kVerification",
    "CategoryStatus",
    "build_jobs",
    "load_manifest",
    "make_ap10k_jobs",
    "verify_ap10k_downloads",
]

__version__ = "0.1.0"
