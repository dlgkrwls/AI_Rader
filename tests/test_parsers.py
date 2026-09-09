"""Parser tests. Fixture in, expected rows out - no network, no DB."""

import json
import unittest
from pathlib import Path

from src.collectors.arxiv import ArxivCollector, _squash

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_sample.xml"

ITEM_COLUMNS = {
    "source", "source_type", "external_id", "title", "summary", "url",
    "authors", "tags", "published_at", "collected_at", "raw_json",
}


class ArxivParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = ArxivCollector().parse(FIXTURE.read_text(encoding="utf-8"))

    def test_parses_every_entry(self):
        self.assertEqual(len(self.items), 2)

    def test_supplies_every_item_column(self):
        for item in self.items:
            self.assertEqual(set(item), ITEM_COLUMNS)

    def test_not_null_columns_are_filled(self):
        for item in self.items:
            for column in ("source", "source_type", "external_id", "title",
                           "url", "collected_at", "raw_json"):
                self.assertTrue(item[column], f"{column} is empty")

    def test_external_id_drops_the_version_suffix(self):
        # Both fixture entries are v1; a v2 revision must map to the same id.
        self.assertEqual(self.items[0]["external_id"], "2609.09082")

    def test_raw_json_keeps_the_versioned_id(self):
        raw = json.loads(self.items[0]["raw_json"])
        self.assertEqual(raw["id"], "http://arxiv.org/abs/2609.09082v1")

    def test_authors_and_tags_are_json_arrays(self):
        for item in self.items:
            self.assertIsInstance(json.loads(item["authors"]), list)
            self.assertIsInstance(json.loads(item["tags"]), list)


class SquashTest(unittest.TestCase):
    def test_collapses_line_wrapping(self):
        self.assertEqual(_squash("a wrapped\n  abstract"), "a wrapped abstract")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(_squash("\n  padded \n"), "padded")


if __name__ == "__main__":
    unittest.main()
