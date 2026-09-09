"""Hugging Face collector. Hub API -> models in items, downloads/likes in metrics."""

import json
import logging
from datetime import datetime, timezone

import requests

from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

MODELS_URL = "https://huggingface.co/api/models"


class HuggingFaceCollector(BaseCollector):
    source = "huggingface"

    def units(self) -> list:
        return self.config["tasks"]

    def fetch(self, unit: str) -> list:
        """List models for one task. Returns the parsed JSON array."""
        response = requests.get(
            MODELS_URL,
            params={
                "filter": unit,
                "sort": self.config["sort"],
                "direction": -1,
                "limit": self.config["max_results_per_task"],
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def parse(self, raw: list) -> list[dict]:
        collected_at = datetime.now(timezone.utc).isoformat()
        items = []
        for model in raw:
            model_id = model["id"]
            owner = model_id.split("/")[0] if "/" in model_id else None
            items.append(
                {
                    "source": self.source,
                    "source_type": "model",
                    "external_id": model_id,
                    "title": model_id,
                    # The list endpoint carries no description; the model card is
                    # a separate request per model. Left empty rather than faked.
                    "summary": None,
                    "url": f"https://huggingface.co/{model_id}",
                    "authors": json.dumps([owner] if owner else []),
                    "tags": json.dumps(model.get("tags", [])),
                    "published_at": model.get("createdAt"),
                    "collected_at": collected_at,
                    "raw_json": json.dumps(model, ensure_ascii=False),
                    "metrics": {
                        "downloads": model["downloads"],
                        "likes": model["likes"],
                    },
                }
            )
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    total_fetched, total_new = HuggingFaceCollector().run()
    print(f"huggingface: fetched={total_fetched} new={total_new}")
