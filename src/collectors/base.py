"""Shared collector skeleton, extracted from the arXiv collector built in T2."""

import logging
import time
from datetime import datetime, timezone

from src.config import load_sources
from src.database.connection import get_connection

logger = logging.getLogger(__name__)

INSERT_ITEM = """
    INSERT OR IGNORE INTO items
        (source, source_type, external_id, title, summary, url,
         authors, tags, published_at, collected_at, raw_json)
    VALUES (:source, :source_type, :external_id, :title, :summary, :url,
            :authors, :tags, :published_at, :collected_at, :raw_json)
"""


class BaseCollector:
    """fetch() -> parse() -> save(), wrapped by run() for bookkeeping.

    Subclasses set `source` and implement units(), fetch() and parse().
    Sources that track changing numbers extend save() to write item_metrics.
    """

    source = ""

    def __init__(self):
        self.config = load_sources()[self.source]
        self.delay_sec = self.config.get("request_delay_sec", 0)

    def units(self) -> list:
        """What to iterate over: categories, search queries, feed URLs."""
        raise NotImplementedError

    def fetch(self, unit):
        """Raw API response for one unit. The only step that touches the network."""
        raise NotImplementedError

    def parse(self, raw) -> list[dict]:
        """Raw response -> item rows. Pure: no network, no DB, no clock beyond now."""
        raise NotImplementedError

    def save(self, conn, items: list[dict]) -> int:
        """Insert items, skipping ones already stored. Returns the new row count."""
        before = conn.total_changes
        conn.executemany(INSERT_ITEM, items)
        conn.commit()
        return conn.total_changes - before

    def run(self) -> tuple[int, int]:
        """Collect every unit and record the outcome. Returns (fetched, new)."""
        started_at = _now()
        fetched = new = 0
        errors = []
        with get_connection() as conn:
            for i, unit in enumerate(self.units()):
                if i and self.delay_sec:
                    time.sleep(self.delay_sec)
                try:
                    items = self.parse(self.fetch(unit))
                    added = self.save(conn, items)
                except Exception as error:
                    # One unit must never take down the rest of the run.
                    logger.exception("%s %s failed", self.source, unit)
                    errors.append(f"{unit}: {error}")
                    continue
                fetched += len(items)
                new += added
                logger.info(
                    "%s %s: fetched=%d new=%d", self.source, unit, len(items), added
                )
            self._record_run(conn, started_at, fetched, new, errors)
        return fetched, new

    def _record_run(self, conn, started_at, fetched, new, errors):
        if not errors:
            status = "success"
        elif fetched:
            status = "partial"
        else:
            status = "failed"
        conn.execute(
            """INSERT INTO collection_runs
               (source, started_at, finished_at, status,
                items_fetched, items_new, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self.source,
                started_at,
                _now(),
                status,
                fetched,
                new,
                "; ".join(errors) or None,
            ),
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
