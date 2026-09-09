"""GitHub collector. Search API -> repositories in items, stars/forks in metrics."""

import json
import logging
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.github.com/search/repositories"


def _token() -> str:
    """Read GITHUB_TOKEN at request time.

    Not in __init__ on purpose: loading the credential there would make the
    collector impossible to construct - and parse() impossible to test - on a
    machine without a token.
    """
    load_dotenv()
    return os.environ["GITHUB_TOKEN"]


class GithubCollector(BaseCollector):
    source = "github"

    def units(self) -> list:
        return self.config["queries"]

    def fetch(self, unit: str) -> dict:
        """Search repositories for one query. Returns the parsed JSON body."""
        response = requests.get(
            SEARCH_URL,
            params={
                "q": f"{unit} stars:>={self.config['min_stars']}",
                "sort": "stars",
                "order": "desc",
                "per_page": self.config["max_results_per_query"],
            },
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {_token()}",
            },
            timeout=30,
        )
        response.raise_for_status()
        # Search has its own budget, separate from the 5000/hour core limit.
        logger.info(
            "github rate limit: %s/%s left",
            response.headers.get("X-RateLimit-Remaining"),
            response.headers.get("X-RateLimit-Limit"),
        )
        return response.json()

    def parse(self, raw: dict) -> list[dict]:
        collected_at = datetime.now(timezone.utc).isoformat()
        items = []
        for repo in raw["items"]:
            items.append(
                {
                    "source": self.source,
                    "source_type": "repo",
                    "external_id": repo["full_name"],
                    "title": repo["full_name"],
                    "summary": repo["description"],
                    "url": repo["html_url"],
                    "authors": json.dumps([repo["owner"]["login"]]),
                    "tags": json.dumps(repo.get("topics", [])),
                    "published_at": repo["created_at"],
                    "collected_at": collected_at,
                    "raw_json": json.dumps(repo, ensure_ascii=False),
                    # Changing numbers never go in items; BaseCollector.save()
                    # appends these to item_metrics.
                    "metrics": {
                        "stars": repo["stargazers_count"],
                        "forks": repo["forks_count"],
                    },
                }
            )
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    total_fetched, total_new = GithubCollector().run()
    print(f"github: fetched={total_fetched} new={total_new}")
