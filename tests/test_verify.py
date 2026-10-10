import tempfile
import unittest
from pathlib import Path

from yt_demand_dl.verify import verify_ap10k_downloads


class VerifyTests(unittest.TestCase):
    def test_verify_ignores_symlinked_files_and_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "downloads"
            root.mkdir()
            external = Path(tmp) / "external"
            external.mkdir()
            (external / "video.mp4").write_bytes(b"outside")
            (external / "video.info.json").write_text(
                '{"height": 2160}',
                encoding="utf-8",
            )

            antelope = root / "antelope"
            antelope.mkdir()
            (antelope / "video.mp4").symlink_to(external / "video.mp4")
            (antelope / "video.info.json").symlink_to(external / "video.info.json")
            (root / "argali_sheep").symlink_to(external, target_is_directory=True)

            result = verify_ap10k_downloads(root, category_limit=2)

        self.assertFalse(result.complete)
        self.assertEqual(result.complete_count, 0)
        self.assertEqual(result.missing, ("antelope", "argali sheep"))
        self.assertIsNone(result.statuses[0].selected_height)
        self.assertIsNone(result.statuses[1].selected_height)

    def test_verify_ap10k_downloads_reports_missing_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "antelope").mkdir()
            (root / "antelope" / "video.mp4").write_bytes(b"fake")
            (root / "antelope" / "video.info.json").write_text(
                '{"height": 1080}',
                encoding="utf-8",
            )
            (root / "archive.txt").write_text("youtube fake\n", encoding="utf-8")

            result = verify_ap10k_downloads(root, category_limit=2)

        self.assertFalse(result.complete)
        self.assertEqual(result.complete_count, 1)
        self.assertEqual(result.expected_count, 2)
        self.assertEqual(result.archive_entries, 1)
        self.assertEqual(result.missing, ("argali sheep",))
        self.assertEqual(result.statuses[0].selected_height, 1080)
        self.assertEqual(result.below_min_height(720), (result.statuses[1],))


if __name__ == "__main__":
    unittest.main()
