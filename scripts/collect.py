"""Run every collector in order.

Minimal on purpose: T7 replaces this with the full orchestration (summary
output, timings). The path stays the same so the scheduler task keeps working.
"""

import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.arxiv import ArxivCollector
from src.collectors.github import GithubCollector
from src.collectors.huggingface import HuggingFaceCollector

COLLECTORS = (ArxivCollector, GithubCollector, HuggingFaceCollector)


def setup_logging() -> Path:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"collect_{date.today().isoformat()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            # utf-8 explicitly: Windows would otherwise use cp949 and blow up on
            # a non-ASCII paper title.
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_path


def main() -> None:
    log_path = setup_logging()
    logging.info("collection started, logging to %s", log_path)
    for collector_class in COLLECTORS:
        try:
            fetched, new = collector_class().run()
            logging.info(
                "%s done: fetched=%d new=%d", collector_class.source, fetched, new
            )
        except Exception:
            # run() already isolates failures per unit; this catches a collector
            # that dies before that, e.g. a missing token or config key.
            logging.exception("%s failed entirely", collector_class.source)
    logging.info("collection finished")


if __name__ == "__main__":
    main()
