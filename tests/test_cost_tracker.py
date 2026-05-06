import json
from pathlib import Path

import pytest

import src.utils.cost_tracker as ct_mod
from src.utils.cost_tracker import CostTracker


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    log = tmp_path / "cost_log.jsonl"
    monkeypatch.setattr(ct_mod, "LOG_FILE", log)
    return CostTracker(), log


def test_single_log_writes_jsonl(tracker):
    t, log = tracker
    t.log("gemini-flash", "research", 1500)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["agent"] == "research"
    assert rec["model"] == "gemini-flash"
    assert rec["tokens"] == 1500


def test_multiple_logs_accumulate(tracker):
    t, log = tracker
    t.log("gemini-flash", "research", 1000)
    t.log("gemini-flash", "expert", 2000)
    t.log("gemini-flash", "translator", 1500)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 3
    assert t.daily_total() > 0


def test_cost_calculation(tracker):
    t, _ = tracker
    # 1M tokens of flash = $0.075 → 1000 tokens = $0.000075
    t.log("gemini-flash", "x", 1_000_000)
    # daily_total rounds to 4 decimals so should be 0.075
    assert t.daily_total() == 0.075


def test_unknown_model_uses_default_price(tracker):
    t, _ = tracker
    t.log("brand-new-model", "x", 1_000_000)
    # falls back to flash price
    assert t.daily_total() == 0.075


def test_per_agent_session_tracking(tracker):
    t, _ = tracker
    t.log("gemini-flash", "research", 1000)
    t.log("gemini-flash", "research", 2000)
    t.log("gemini-flash", "expert", 1500)
    # 3000 + 1500 = 4500 tokens × $0.075/1M
    expected = 4500 * 0.075 / 1_000_000
    assert abs(t.daily_total() - round(expected, 4)) < 0.0001
