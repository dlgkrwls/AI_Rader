"""SQLite connection helper."""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "radar.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection to the radar database, creating the data dir if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Off by default in SQLite; item_metrics.item_id must point at a real item.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
