import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
LOG_FILE = Path("data/cost_log.jsonl")
PRICE_PER_1M = {"gemini-flash": 0.075, "gemini-pro": 3.50}


class CostTracker:
    def __init__(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._session = {}

    def log(self, model: str, agent: str, tokens: int):
        cost = PRICE_PER_1M.get(model, 0.075) * tokens / 1_000_000
        self._session[f"{model}:{agent}"] = self._session.get(f"{model}:{agent}", 0) + cost
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(),
                "model": model, "agent": agent,
                "tokens": tokens, "cost_usd": round(cost, 6)
            }) + "\n")

    def daily_total(self) -> float:
        return round(sum(self._session.values()), 4)
