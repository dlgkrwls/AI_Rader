"""Parser tests. Fixture in, expected rows out - no network, no DB."""

import json
import unittest
from pathlib import Path

from src.collectors.arxiv import ArxivCollector, _squash
from src.collectors.base import ITEM_COLUMNS
from src.collectors.github import GithubCollector

FIXTURES = Path(__file__).parent / "fixtures"


class ArxivParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (FIXTURES / "arxiv_sample.xml").read_text(encoding="utf-8")
        cls.items = ArxivCollector().parse(raw)

    def test_parses_every_entry(self):
        self.assertEqual(len(self.items), 2)

    def test_supplies_every_item_column(self):
        for item in self.items:
            self.assertEqual(set(item), set(ITEM_COLUMNS))

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


class GithubParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Constructing the collector must not need a token, or this cannot run.
        raw = json.loads((FIXTURES / "github_sample.json").read_text(encoding="utf-8"))
        cls.items = GithubCollector().parse(raw)

    def test_parses_every_repo(self):
        self.assertEqual(len(self.items), 2)

    def test_carries_item_columns_plus_metrics(self):
        for item in self.items:
            self.assertEqual(set(item), set(ITEM_COLUMNS) | {"metrics"})

    def test_external_id_is_owner_slash_repo(self):
        self.assertEqual(self.items[0]["external_id"], "m87-labs/moondream")

    def test_metrics_hold_stars_and_forks(self):
        metrics = self.items[0]["metrics"]
        self.assertEqual(set(metrics), {"stars", "forks"})
        for value in metrics.values():
            self.assertIsInstance(value, int)

    def test_changing_numbers_stay_out_of_the_item_columns(self):
        # stars/forks belong in item_metrics. Only raw_json may echo them.
        for item in self.items:
            columns = {c: item[c] for c in ITEM_COLUMNS if c != "raw_json"}
            self.assertNotIn(str(item["metrics"]["stars"]), json.dumps(columns))

    def test_raw_json_round_trips(self):
        raw = json.loads(self.items[0]["raw_json"])
        self.assertEqual(raw["full_name"], "m87-labs/moondream")


class SquashTest(unittest.TestCase):
    def test_collapses_line_wrapping(self):
        self.assertEqual(_squash("a wrapped\n  abstract"), "a wrapped abstract")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(_squash("\n  padded \n"), "padded")


if __name__ == "__main__":
    unittest.main()
