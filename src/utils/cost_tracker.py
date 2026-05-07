"""
Cost tracker — per-model input/output pricing.
Each generate call writes one JSONL line so the daily artifact reflects
real spend, not a guess.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
LOG_FILE = Path("data/cost_log.jsonl")

# USD per 1M tokens, (input, output). Public Gemini pricing as of mid-2025;
# update when prices change.
PRICING = {
    "gemini-2.0-flash":        (0.075, 0.30),
    "gemini-2.0-flash-lite":   (0.075, 0.30),
    "gemini-1.5-flash":        (0.075, 0.30),
    "gemini-1.5-flash-8b":     (0.0375, 0.15),
    "gemini-2.5-flash":        (0.30,  2.50),
    "gemini-2.5-flash-lite":   (0.10,  0.40),
    "gemini-2.5-pro":          (1.25,  10.00),
    "gemini-1.5-pro":          (1.25,  5.00),
}
DEFAULT_PRICE = (0.075, 0.30)


class CostTracker:
    def __init__(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._session: dict[str, float] = {}

    def log(self, model: str, agent: str,
            in_tokens: int, out_tokens: int = 0):
        in_rate, out_rate = PRICING.get(model, DEFAULT_PRICE)
        cost = (in_tokens * in_rate + out_tokens * out_rate) / 1_000_000
        key = f"{model}:{agent}"
        self._session[key] = self._session.get(key, 0) + cost
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(),
                "model": model, "agent": agent,
                "in_tokens": in_tokens, "out_tokens": out_tokens,
                "cost_usd": round(cost, 6),
            }) + "\n")

    def daily_total(self) -> float:
        return round(sum(self._session.values()), 4)
