"""arXiv collector. Reads the Atom API and stores papers in items."""

import json
import logging
import re
from datetime import datetime, timezone

import feedparser
import requests

from src.collectors.base import BaseCollector

API_URL = "http://export.arxiv.org/api/query"

# "http://arxiv.org/abs/2509.01234v2" -> "2509.01234". The version is dropped so a
# revised paper stays one row instead of becoming a second item; the versioned id
# is still preserved inside raw_json.
ARXIV_ID_RE = re.compile(r"abs/(.+?)(v\d+)?$")


class ArxivCollector(BaseCollector):
    source = "arxiv"

    def units(self) -> list:
        return self.config["categories"]

    def fetch(self, unit: str) -> str:
        """Request the newest papers of one category. Returns the raw Atom feed."""
        params = {
            "search_query": f"cat:{unit}",
            "start": 0,
            "max_results": self.config["max_results"],
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.text

    def parse(self, raw: str) -> list[dict]:
        feed = feedparser.parse(raw)
        collected_at = datetime.now(timezone.utc).isoformat()
        items = []
        for entry in feed.entries:
            match = ARXIV_ID_RE.search(entry.id)
            items.append(
                {
                    "source": self.source,
                    "source_type": "paper",
                    "external_id": match.group(1) if match else entry.id,
                    # arXiv wraps titles and abstracts at ~80 chars, so both
                    # arrive full of newlines and runs of spaces.
                    "title": _squash(entry.title),
                    "summary": _squash(entry.summary),
                    "url": entry.link,
                    "authors": json.dumps([a.name for a in entry.get("authors", [])]),
                    "tags": json.dumps([t.term for t in entry.get("tags", [])]),
                    "published_at": entry.get("published"),
                    "collected_at": collected_at,
                    # default=str because feedparser adds time.struct_time fields
                    # that json cannot serialize on its own.
                    "raw_json": json.dumps(entry, default=str, ensure_ascii=False),
                }
            )
        return items


def _squash(text: str) -> str:
    """Collapse the feed's hard line wrapping into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    total_fetched, total_new = ArxivCollector().run()
    print(f"arxiv: fetched={total_fetched} new={total_new}")
