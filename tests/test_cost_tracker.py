import json

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
    t.log("gemini-2.0-flash", "research", 1000, 500)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["agent"] == "research"
    assert rec["model"] == "gemini-2.0-flash"
    assert rec["in_tokens"] == 1000
    assert rec["out_tokens"] == 500


def test_input_only_log_works():
    """Backward compat: out_tokens defaults to 0."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        ct_mod.LOG_FILE = Path(tmp) / "cost.jsonl"
        t = CostTracker()
        t.log("gemini-2.0-flash", "x", 1000)
        # Shouldn't blow up; just charges input rate
        assert t.daily_total() > 0


def test_input_output_pricing_calculation(tracker):
    t, _ = tracker
    # gemini-2.0-flash: $0.075/M in, $0.30/M out
    # 1M in + 1M out → 0.075 + 0.30 = 0.375
    t.log("gemini-2.0-flash", "x", 1_000_000, 1_000_000)
    assert t.daily_total() == 0.375


def test_pro_more_expensive_than_flash(tracker):
    t, _ = tracker
    t.log("gemini-2.5-pro", "x", 100_000, 100_000)
    pro_cost = t.daily_total()

    t2, _ = tracker  # same fixture, same session — drop and rebuild
    t._session.clear()
    t.log("gemini-2.0-flash", "x", 100_000, 100_000)
    flash_cost = t.daily_total()

    assert pro_cost > flash_cost * 10  # Pro is ~30x flash on output


def test_unknown_model_uses_default_price(tracker):
    t, _ = tracker
    t.log("brand-new-model-xyz", "x", 1_000_000)
    assert t.daily_total() == 0.075  # default flash input rate


def test_multiple_logs_accumulate(tracker):
    t, log = tracker
    t.log("gemini-2.0-flash", "research", 1000, 500)
    t.log("gemini-2.0-flash", "expert", 2000, 1000)
    t.log("gemini-2.0-flash", "translator", 1500, 800)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 3
    assert t.daily_total() > 0


def test_log_records_zero_output_when_input_only(tracker):
    t, log = tracker
    t.log("gemini-2.0-flash", "x", 1000)
    rec = json.loads(log.read_text().strip())
    assert rec["in_tokens"] == 1000
    assert rec["out_tokens"] == 0
