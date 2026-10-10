import io
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from yt_demand_dl import cli


class CliTests(unittest.TestCase):
    def test_rejects_invalid_numeric_download_options(self):
        for args in (
            ["download", "query", "--query", "--limit", "0"],
            ["ap10k", "--videos-per-category", "0"],
            ["download", "query", "--max-duration", "-1"],
            ["download", "query", "--socket-timeout", "0"],
        ):
            with self.subTest(args=args):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(args)
                self.assertEqual(2, raised.exception.code)

    def test_rejects_output_template_path_escape(self):
        with self.assertRaises(SystemExit) as raised:
            cli.main(["download", "query", "--output-template", "../escape.mp4"])
        self.assertEqual(2, raised.exception.code)

    def test_list_ap10k_limit(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["list-ap10k", "--limit", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().splitlines(), ["antelope", "argali sheep", "bison"])

    def test_ap10k_dry_run_invokes_53_jobs(self):
        calls = []

        class FakeBackend:
            def download(self, job):
                calls.append(job)
                return type(
                    "Result",
                    (),
                    {"item_count": 1, "downloaded": False},
                )()

        out = io.StringIO()
        with patch.object(cli, "YtDlpBackend", return_value=FakeBackend()):
            with redirect_stdout(out):
                code = cli.main(["ap10k", "--dry-run", "--category-limit", "53"])

        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 53)
        self.assertEqual(calls[0].demand.resolved_source(), "ytsearch1:antelope animal video")
        self.assertIn("downloaded=False", out.getvalue())

    def test_ap10k_plan_only_does_not_construct_backend(self):
        out = io.StringIO()
        with patch.object(cli, "YtDlpBackend") as backend_cls:
            with redirect_stdout(out):
                code = cli.main(["ap10k", "--plan-only", "--category-limit", "2"])

        self.assertEqual(code, 0)
        backend_cls.assert_not_called()
        self.assertEqual(
            out.getvalue().splitlines(),
            [
                "antelope: ytsearch1:antelope animal video",
                "argali sheep: ytsearch1:argali sheep animal video",
            ],
        )

    def test_verify_ap10k_writes_missing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "downloads"
            missing = Path(tmp) / "missing.txt"
            (root / "antelope").mkdir(parents=True)
            (root / "antelope" / "video.mp4").write_bytes(b"fake")
            (root / "antelope" / "video.info.json").write_text(
                '{"height": 1080}',
                encoding="utf-8",
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(
                    [
                        "verify-ap10k",
                        str(root),
                        "--category-limit",
                        "2",
                        "--missing-output",
                        str(missing),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(missing.read_text(encoding="utf-8"), "argali sheep\n")

    def test_resume_ap10k_downloads_only_missing_categories(self):
        calls = []

        class FakeBackend:
            def download(self, job):
                calls.append(job)
                return type("Result", (), {"item_count": 1, "downloaded": True})()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "downloads"
            (root / "antelope").mkdir(parents=True)
            (root / "antelope" / "video.mp4").write_bytes(b"fake")
            out = io.StringIO()
            with patch.object(cli, "YtDlpBackend", return_value=FakeBackend()):
                with redirect_stdout(out):
                    code = cli.main(
                        [
                            "resume-ap10k",
                            str(root),
                            "--category-limit",
                            "2",
                            "--dry-run",
                        ]
                    )

        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].label, "argali sheep")
        self.assertEqual(calls[0].options.output_dir, root)


if __name__ == "__main__":
    unittest.main()
