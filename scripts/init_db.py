"""Create data/radar.db with the Phase 1 schema. Safe to re-run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database.connection import DB_PATH, get_connection
from src.database.schema import init_schema


def main() -> None:
    with get_connection() as conn:
        init_schema(conn)
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
    print(f"{DB_PATH} ready: {', '.join(tables)}")


if __name__ == "__main__":
    main()
