import os
import tempfile
import unittest
from pathlib import Path

from yt_demand_dl.ap10k import make_ap10k_jobs
from yt_demand_dl.backends import YtDlpBackend
from yt_demand_dl.models import DownloadOptions
from yt_demand_dl.planner import build_jobs


@unittest.skipUnless(
    os.environ.get("YT_DEMAND_DL_RUN_NETWORK") == "1",
    "set YT_DEMAND_DL_RUN_NETWORK=1 to run real YouTube downloads",
)
class YoutubeIntegrationTests(unittest.TestCase):
    def test_download_ap10k_53_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = DownloadOptions(
                output_dir=Path(tmp),
                format_selector="worst[ext=mp4]/worst",
                max_duration=180,
                max_filesize="20M",
                write_info_json=True,
                quiet=True,
                cookies=Path(os.environ["YT_DEMAND_DL_COOKIES"])
                if os.environ.get("YT_DEMAND_DL_COOKIES")
                else None,
            )
            demands = make_ap10k_jobs(category_limit=53, videos_per_category=1)
            results = [
                YtDlpBackend().download(job)
                for job in build_jobs(demands, options)
            ]

            self.assertEqual(len(results), 53)
            self.assertTrue(all(result.item_count >= 1 for result in results))


if __name__ == "__main__":
    unittest.main()
