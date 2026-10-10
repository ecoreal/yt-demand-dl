import tempfile
import unittest
from pathlib import Path

from yt_demand_dl.manifest import load_manifest


class ManifestTests(unittest.TestCase):
    def test_invalid_rows_include_line_context(self):
        cases = (
            ("{broken", "invalid JSON"),
            ('{"source": ""}', "source must be a non-empty string"),
            ('{"source": "x", "limit": 0}', "limit must be a positive integer"),
            ('{"source": "x", "search_prefix": ""}', "search_prefix must be a non-empty string"),
            ('{"source": "x", "query": "false"}', "query must be a boolean"),
            ('{"source": "x", "limit": 1.5}', "limit must be a positive integer"),
        )
        for row, message in cases:
            with self.subTest(row=row), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "manifest.jsonl"
                path.write_text(row + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, rf"{path}:1:.*{message}"):
                    load_manifest(path)

    def test_load_jsonl_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            path.write_text(
                '# comment\n'
                '{"label": "badger", "source": "https://youtu.be/example"}\n'
                '{"label": "squirrel", "source": "squirrel animal video", "query": true, "limit": 2}\n',
                encoding="utf-8",
            )
            demands = load_manifest(path)

        self.assertEqual(len(demands), 2)
        self.assertEqual(demands[0].label, "badger")
        self.assertEqual(demands[0].resolved_source(), "https://youtu.be/example")
        self.assertEqual(demands[1].resolved_source(), "ytsearch2:squirrel animal video")


if __name__ == "__main__":
    unittest.main()
