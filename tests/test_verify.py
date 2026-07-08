import tempfile
import unittest
from pathlib import Path

from yt_demand_dl.verify import verify_ap10k_downloads


class VerifyTests(unittest.TestCase):
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
