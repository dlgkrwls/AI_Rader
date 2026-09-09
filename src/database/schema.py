"""Table definitions. See docs/SCHEMA.md for the design rationale."""

import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY,
    source          TEXT NOT NULL,        -- arxiv | github | huggingface | blog
    source_type     TEXT NOT NULL,        -- paper | repo | model | announcement
    external_id     TEXT NOT NULL,        -- arXiv ID, owner/repo, model path, URL
    title           TEXT NOT NULL,
    summary         TEXT,                 -- abstract / description / excerpt
    url             TEXT NOT NULL,
    authors         TEXT,                 -- JSON array
    tags            TEXT,                 -- JSON array (categories, topics, tags)
    published_at    TIMESTAMP,            -- when the source published it
    collected_at    TIMESTAMP NOT NULL,   -- when we collected it
    raw_json        TEXT NOT NULL,        -- full original API response
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source, published_at DESC);

-- Append-only time series. Never UPDATE a row here.
CREATE TABLE IF NOT EXISTS item_metrics (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES items(id),
    metric      TEXT NOT NULL,        -- stars | forks | downloads | likes
    value       REAL NOT NULL,
    recorded_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_item
    ON item_metrics(item_id, metric, recorded_at);

CREATE TABLE IF NOT EXISTS collection_runs (
    id             INTEGER PRIMARY KEY,
    source         TEXT NOT NULL,
    started_at     TIMESTAMP NOT NULL,
    finished_at    TIMESTAMP,
    status         TEXT NOT NULL,     -- success | partial | failed
    items_fetched  INTEGER DEFAULT 0,
    items_new      INTEGER DEFAULT 0,
    error_message  TEXT
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes. Idempotent - safe to run repeatedly."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
