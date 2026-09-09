"""arXiv collector. Reads the Atom API and stores papers in items."""

import json
import logging
import re
import time
from datetime import datetime, timezone

import feedparser
import requests

from src.config import load_sources
from src.database.connection import get_connection

logger = logging.getLogger(__name__)

API_URL = "http://export.arxiv.org/api/query"

# "http://arxiv.org/abs/2509.01234v2" -> "2509.01234". The version is dropped so a
# revised paper stays one row instead of becoming a second item; the versioned id
# is still preserved inside raw_json.
ARXIV_ID_RE = re.compile(r"abs/(.+?)(v\d+)?$")


def fetch(category: str, max_results: int) -> str:
    """Request the newest papers of one category. Returns the raw Atom feed."""
    params = {
        "search_query": f"cat:{category}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.text


def parse(feed_text: str) -> list[dict]:
    """Turn an Atom feed into item rows. Pure function - no network, no DB."""
    feed = feedparser.parse(feed_text)
    collected_at = datetime.now(timezone.utc).isoformat()
    items = []
    for entry in feed.entries:
        match = ARXIV_ID_RE.search(entry.id)
        items.append(
            {
                "source": "arxiv",
                "source_type": "paper",
                "external_id": match.group(1) if match else entry.id,
                # arXiv wraps titles and abstracts at ~80 chars, so both arrive
                # full of newlines and runs of spaces.
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


def save(conn, items: list[dict]) -> int:
    """Insert items, skipping ones already stored. Returns the new row count."""
    before = conn.total_changes
    conn.executemany(
        """INSERT OR IGNORE INTO items
           (source, source_type, external_id, title, summary, url,
            authors, tags, published_at, collected_at, raw_json)
           VALUES (:source, :source_type, :external_id, :title, :summary, :url,
                   :authors, :tags, :published_at, :collected_at, :raw_json)""",
        items,
    )
    conn.commit()
    return conn.total_changes - before


def collect() -> tuple[int, int]:
    """Run the collector over every configured category. Returns (fetched, new)."""
    config = load_sources()["arxiv"]
    fetched = new = 0
    with get_connection() as conn:
        for i, category in enumerate(config["categories"]):
            if i > 0:
                # arXiv asks for one request per 3s; ignoring it gets us blocked.
                time.sleep(config["request_delay_sec"])
            items = parse(fetch(category, config["max_results"]))
            added = save(conn, items)
            fetched += len(items)
            new += added
            logger.info("arxiv %s: fetched=%d new=%d", category, len(items), added)
    return fetched, new


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    total_fetched, total_new = collect()
    print(f"arxiv: fetched={total_fetched} new={total_new}")
