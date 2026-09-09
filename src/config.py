"""Access to config/sources.yaml."""

import yaml

from src.database.connection import PROJECT_ROOT

SOURCES_PATH = PROJECT_ROOT / "config" / "sources.yaml"


def load_sources() -> dict:
    """Load the collection source definitions."""
    with open(SOURCES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
