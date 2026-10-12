import json
import tempfile
import unittest
from pathlib import Path

from yt_demand_dl.ap10k import AP10K_CATEGORIES, load_categories, make_ap10k_jobs


class Ap10kTests(unittest.TestCase):
    def test_bundled_categories_have_official_54_count(self):
        self.assertEqual(len(AP10K_CATEGORIES), 54)
        self.assertEqual(len(set(name.lower() for name in AP10K_CATEGORIES)), 54)

    def test_default_ap10k_jobs_match_requested_53_categories(self):
        jobs = make_ap10k_jobs()
        self.assertEqual(len(jobs), 53)
        self.assertEqual(jobs[0].resolved_source(), "ytsearch1:antelope animal video")
        self.assertEqual(jobs[-1].label, "raccoon")

    def test_ap10k_jobs_can_use_all_54_categories(self):
        jobs = make_ap10k_jobs(category_limit=None, videos_per_category=2)
        self.assertEqual(len(jobs), 54)
        self.assertEqual(jobs[-1].resolved_source(), "ytsearch2:killer whale animal video")

    def test_query_template_requires_category_field_and_handles_malformed_input(self):
        for template in ("animal video", "{unknown}", "{category"):
            with self.subTest(template=template):
                with self.assertRaises(ValueError):
                    make_ap10k_jobs(category_limit=1, query_template=template)

    def test_load_categories_rejects_malformed_structured_input(self):
        cases = (
            '{"categories": "not-an-array"}',
            '{"categories": [{"name": ""}]}',
            '[{"id": 1}]',
            '["wolf", 3]',
            '[]',
        )
        for content in cases:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "categories.json"
                path.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, str(path)):
                    load_categories(path)

    def test_load_categories_from_coco_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "annotations.json"
            path.write_text(
                json.dumps(
                    {
                        "categories": [
                            {"id": 1, "name": "antelope"},
                            {"id": 2, "name": "antelope"},
                            {"id": 3, "name": "wolf"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_categories(path), ("antelope", "wolf"))

    def test_load_categories_strips_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "annotations.json"
            json_path.write_text(
                json.dumps({"categories": [{"id": 1, "name": "wolf"}]}),
                encoding="utf-8-sig",
            )
            text_path = Path(tmp) / "categories.txt"
            text_path.write_text("wolf\r\nfox\r\n", encoding="utf-8-sig")

            self.assertEqual(load_categories(json_path), ("wolf",))
            self.assertEqual(load_categories(text_path), ("wolf", "fox"))


if __name__ == "__main__":
    unittest.main()
