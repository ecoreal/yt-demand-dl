import tempfile
import unittest
from pathlib import Path

from yt_demand_dl.manifest import MAX_MANIFEST_BYTES, MAX_MANIFEST_ROWS, load_manifest


class ManifestTests(unittest.TestCase):
    def test_invalid_rows_include_line_context(self):
        cases = (
            ("{broken", "invalid JSON"),
            ('{"source": ""}', "source must be a non-empty string"),
            ('{"source": "x", "limit": 0}', "limit must be a positive integer"),
            ('{"source": "x", "search_prefix": ""}', "search_prefix must be a non-empty string"),
            ('{"source": "x", "query": "false"}', "query must be a boolean"),
            ('{"source": "x", "limit": 1.5}', "limit must be a positive integer"),
            ('{"source": "x", "metadata": null}', "metadata must be an object"),
            ('{"source": "x", "metadata": false}', "metadata must be an object"),
            ('{"source": "x", "metadata": []}', "metadata must be an object"),
        )
        for row, message in cases:
            with self.subTest(row=row), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "manifest.jsonl"
                path.write_text(row + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, rf"{path}:1:.*{message}"):
                    load_manifest(path)

    def test_rejects_symlinked_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.jsonl"
            real.write_text('{"source": "x"}\n', encoding="utf-8")
            link = root / "link.jsonl"
            link.symlink_to(real)
            with self.assertRaisesRegex(ValueError, "symlinked manifest"):
                load_manifest(link)

    def test_rejects_non_file_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "regular file"):
                load_manifest(Path(tmp))

    def test_rejects_oversized_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            path.write_bytes(b"x" * (MAX_MANIFEST_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "exceeding"):
                load_manifest(path)

    def test_rejects_too_many_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            path.write_text('{"source": "x"}\n' * (MAX_MANIFEST_ROWS + 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "more than"):
                load_manifest(path)

    def test_rejects_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            path.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
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

    def test_manifest_tolerates_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            path.write_text(
                '{"label": "badger", "source": "https://youtu.be/example"}\n',
                encoding="utf-8-sig",
            )

            demands = load_manifest(path)

        self.assertEqual(len(demands), 1)
        self.assertEqual(demands[0].source, "https://youtu.be/example")

    def test_manifest_keeps_rejecting_non_utf8_encodings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            path.write_text(
                '{"label": "badger", "source": "https://youtu.be/example"}\n',
                encoding="utf-16",
            )

            with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
