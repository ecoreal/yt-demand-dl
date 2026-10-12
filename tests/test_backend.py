import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from yt_demand_dl.backends.yt_dlp_backend import YtDlpBackend, _parse_filesize
from yt_demand_dl.filters import duration_rejection_reason
from yt_demand_dl.models import DownloadJob, DownloadOptions, VideoDemand
from yt_demand_dl.planner import build_jobs, safe_label


class ArchiveWritingYoutubeDL:
    calls = []

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, source, download):
        archive = Path(self.options["download_archive"])
        self.__class__.calls.append(archive)
        archive.write_text("youtube video\n", encoding="utf-8")
        return {"id": "video-1"}


class ConcurrentArchiveYoutubeDL:
    guard = threading.Lock()
    active = 0
    maximum_active = 0

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, source, download):
        archive = Path(self.options["download_archive"])
        with self.guard:
            self.__class__.active += 1
            self.__class__.maximum_active = max(
                self.__class__.maximum_active, self.__class__.active
            )
        try:
            time.sleep(0.02)
            with archive.open("a", encoding="utf-8") as handle:
                handle.write(f"{source}\n")
            return {"id": source}
        finally:
            with self.guard:
                self.__class__.active -= 1


class FakeYoutubeDL:
    calls = []

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, source, download):
        self.__class__.calls.append((source, download, self.options))
        if download:
            for hook in self.options.get("progress_hooks", []):
                hook({"status": "finished", "filename": "/tmp/fake-video.mp4"})
        return {"entries": [{"id": "video-1"}, {"id": "video-2"}]}


class BackendTests(unittest.TestCase):
    def setUp(self):
        FakeYoutubeDL.calls = []

    def test_filesize_parser_rejects_invalid_or_non_positive_values(self):
        self.assertEqual(_parse_filesize("1.5M"), 1_572_864)
        for value in ("0", "-1M", "nan", "inf", "not-a-size"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _parse_filesize(value)

    def test_safe_label(self):
        self.assertEqual(safe_label("Snow Leopard"), "snow_leopard")
        self.assertEqual(safe_label("  "), "unlabeled")
        self.assertEqual(safe_label(".."), "unlabeled")

    def test_output_template_cannot_escape_output_directory(self):
        for template in (
            "../escape.mp4",
            "/tmp/escape.mp4",
            "nested/../../escape.mp4",
            r"..\escape.mp4",
            r"C:\escape.mp4",
            r"\\server\share\escape.mp4",
        ):
            with self.subTest(template=template):
                with self.assertRaisesRegex(ValueError, "output_template"):
                    DownloadOptions(output_template=template)

    def test_download_options_validate_api_boundaries(self):
        invalid_options = (
            {"format_selector": ""},
            {"max_duration": 0},
            {"max_duration": True},
            {"min_duration": -1},
            {"min_duration": 11, "max_duration": 10},
            {"max_filesize": "0"},
            {"max_filesize": "not-a-size"},
            {"socket_timeout": 0},
            {"socket_timeout": float("nan")},
            {"socket_timeout": float("inf")},
            {"retries": -1},
            {"retries": True},
            {"fragment_retries": -1},
            {"subtitle_languages": ("en", " ")},
        )
        for kwargs in invalid_options:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                DownloadOptions(**kwargs)

        options = DownloadOptions(
            min_duration=0,
            max_duration=1,
            max_filesize="1.5M",
            socket_timeout=0.1,
            retries=0,
            fragment_retries=0,
        )
        self.assertEqual(options.max_filesize, "1.5M")

    def test_download_archive_is_staged_and_atomically_committed(self):
        ArchiveWritingYoutubeDL.calls = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "state" / "downloaded.txt"
            options = DownloadOptions(
                output_dir=root / "downloads",
                download_archive=archive,
            )
            job = DownloadJob(VideoDemand(source="https://youtu.be/example"), options)

            YtDlpBackend(ArchiveWritingYoutubeDL).download(job)

            self.assertTrue(archive.parent.is_dir())
            self.assertEqual(archive.read_text(encoding="utf-8"), "youtube video\n")
            self.assertNotEqual(ArchiveWritingYoutubeDL.calls[0], archive)
            self.assertEqual(list(archive.parent.glob(".downloaded.txt.*.tmp")), [])
            self.assertTrue((archive.parent / ".downloaded.txt.lock").exists())

    def test_download_archive_serializes_concurrent_jobs(self):
        ConcurrentArchiveYoutubeDL.active = 0
        ConcurrentArchiveYoutubeDL.maximum_active = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "state" / "downloaded.txt"
            options = DownloadOptions(
                output_dir=root / "downloads",
                download_archive=archive,
            )
            jobs = [
                DownloadJob(VideoDemand(source="one"), options),
                DownloadJob(VideoDemand(source="two"), options),
            ]
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(
                    executor.map(
                        lambda job: YtDlpBackend(ConcurrentArchiveYoutubeDL).download(job),
                        jobs,
                    )
                )

            # The lock guarantees mutual exclusion, not a completion order, so
            # compare the staged lines without assuming which job ran first.
            self.assertEqual(ConcurrentArchiveYoutubeDL.maximum_active, 1)
            self.assertEqual(
                sorted(archive.read_text(encoding="utf-8").splitlines()),
                ["one", "two"],
            )

    def test_download_archive_is_serialized_even_when_commit_order_inverts(self):
        # Deterministically let the second-submitted job take the archive lock
        # first, so the committed order is the reverse of the submission order.
        # Both entries must survive and the lock must admit one job at a time.
        started = threading.Event()
        release = threading.Event()
        state = {"active": 0, "maximum_active": 0}
        guard = threading.Lock()

        class PausingYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, source, download):
                with guard:
                    state["active"] += 1
                    state["maximum_active"] = max(state["maximum_active"], state["active"])
                try:
                    archive = Path(self.options["download_archive"])
                    if source == "two":
                        # "two" holds the archive lock while it writes.
                        started.set()
                        if not release.wait(10):
                            raise AssertionError("test never released the first job")
                    with archive.open("a", encoding="utf-8") as handle:
                        handle.write(f"{source}\n")
                    return {"id": source}
                finally:
                    with guard:
                        state["active"] -= 1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "state" / "downloaded.txt"
            options = DownloadOptions(
                output_dir=root / "downloads",
                download_archive=archive,
            )
            jobs = [
                DownloadJob(VideoDemand(source="one"), options),
                DownloadJob(VideoDemand(source="two"), options),
            ]
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(YtDlpBackend(PausingYoutubeDL).download, jobs[1])
                self.assertTrue(started.wait(10))
                second = executor.submit(YtDlpBackend(PausingYoutubeDL).download, jobs[0])
                release.set()
                first.result(10)
                second.result(10)

            self.assertEqual(state["maximum_active"], 1)
            self.assertEqual(
                sorted(archive.read_text(encoding="utf-8").splitlines()),
                ["one", "two"],
            )

    def test_cookies_from_browser_matches_yt_dlp_browser_spec(self):
        def backend_options(value):
            options = DownloadOptions(cookies_from_browser=value)
            return YtDlpBackend(FakeYoutubeDL).build_options(options)["cookiesfrombrowser"]

        self.assertEqual(backend_options("chrome"), ("chrome", None, None, None))
        self.assertEqual(
            backend_options("firefox:default"),
            ("firefox", "default", None, None),
        )
        self.assertEqual(
            backend_options("firefox::Meta"),
            ("firefox", None, None, "Meta"),
        )
        self.assertEqual(
            backend_options("chrome+gnomekeyring:Profile 2::Default"),
            ("chrome", "Profile 2", "GNOMEKEYRING", "Default"),
        )

    def test_cookies_from_browser_rejects_malformed_spec(self):
        invalid = (
            "not a browser!",
            "chrome:",
            "chrome+",
            ":default",
            "chrome+:::",
        )
        for value in invalid:
            with self.subTest(value=value):
                options = DownloadOptions(cookies_from_browser=value)
                with self.assertRaises(ValueError):
                    YtDlpBackend(FakeYoutubeDL).build_options(options)
        # The invalid spec still reaches the backend: only the built yt-dlp
        # options are rejected, so a user-visible error is produced at build time.
        self.assertEqual(
            DownloadOptions(cookies_from_browser="not a browser!").cookies_from_browser,
            "not a browser!",
        )

    def test_duration_filter_rejects_too_long_videos(self):
        options = DownloadOptions(max_duration=30)
        self.assertEqual(
            duration_rejection_reason({"duration": 31}, options),
            "duration 31s is longer than 30s",
        )

    def test_labelled_jobs_preserve_all_download_options(self):
        options = DownloadOptions(
            output_dir=Path("downloads"),
            format_selector="worst",
            dry_run=True,
            max_duration=120,
            min_duration=5,
            max_filesize="20M",
            write_info_json=False,
            write_subtitles=True,
            write_auto_subtitles=True,
            subtitle_languages=("en", "zh-Hans"),
            download_archive=Path("archive.txt"),
            cookies=Path("cookies.txt"),
            cookies_from_browser="chrome",
            proxy="http://127.0.0.1:2266",
            socket_timeout=15,
            retries=2,
            fragment_retries=3,
            no_playlist=False,
            quiet=True,
        )
        job = build_jobs([VideoDemand(source="query", label="Snow Leopard")], options)[0]

        self.assertEqual(job.options.output_template, "snow_leopard/%(title).200B-%(id)s.%(ext)s")
        for field in (
            "output_dir", "format_selector", "dry_run", "max_duration", "min_duration",
            "max_filesize", "write_info_json", "write_subtitles", "write_auto_subtitles",
            "subtitle_languages", "download_archive", "cookies", "cookies_from_browser",
            "proxy", "socket_timeout", "retries", "fragment_retries", "no_playlist", "quiet",
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(job.options, field), getattr(options, field))

    def test_backend_uses_yt_dlp_style_options_without_downloading_on_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = DownloadOptions(
                output_dir=Path(tmp),
                dry_run=True,
                max_duration=120,
                max_filesize="20M",
                cookies=Path("/tmp/cookies.txt"),
                proxy="http://127.0.0.1:2266",
                socket_timeout=15,
                retries=2,
                fragment_retries=3,
            )
            demand = VideoDemand(
                source="snow leopard animal video",
                label="snow leopard",
                query=True,
                limit=2,
            )
            job = build_jobs([demand], options)[0]
            result = YtDlpBackend(FakeYoutubeDL).download(job)

        self.assertEqual(result.ids, ("video-1", "video-2"))
        self.assertFalse(result.downloaded)
        self.assertEqual(result.item_count, 2)
        source, download, ydl_options = FakeYoutubeDL.calls[0]
        self.assertEqual(source, "ytsearch2:snow leopard animal video")
        self.assertFalse(download)
        self.assertTrue(ydl_options["simulate"])
        self.assertTrue(ydl_options["skip_download"])
        self.assertFalse(ydl_options["noprogress"])
        self.assertEqual(ydl_options["max_filesize"], 20 * 1024 * 1024)
        self.assertEqual(ydl_options["cookiefile"], "/tmp/cookies.txt")
        self.assertEqual(ydl_options["proxy"], "http://127.0.0.1:2266")
        self.assertEqual(ydl_options["socket_timeout"], 15)
        self.assertEqual(ydl_options["retries"], 2)
        self.assertEqual(ydl_options["fragment_retries"], 3)
        self.assertIn("snow_leopard", ydl_options["outtmpl"])

    def test_backend_counts_real_media_files_for_non_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            label_dir = output_dir / "wolf"
            label_dir.mkdir()
            (label_dir / "wolf-video.mp4").write_bytes(b"fake")
            options = DownloadOptions(output_dir=output_dir, dry_run=False)
            demand = VideoDemand(source="https://youtu.be/example", label="wolf")
            job = build_jobs([demand], options)[0]
            result = YtDlpBackend(FakeYoutubeDL).download(job)

        self.assertTrue(result.downloaded)
        self.assertEqual(result.item_count, 1)
        self.assertEqual(result.files[0].name, "wolf-video.mp4")


if __name__ == "__main__":
    unittest.main()
