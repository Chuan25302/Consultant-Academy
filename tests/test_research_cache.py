import os
import time
from pathlib import Path

import pytest

import src.integrations.research_cache as rc_mod
from src.integrations.research_cache import ResearchCache


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(rc_mod, "CACHE_DIR", tmp_path)
    return ResearchCache(ttl_days=7)


def test_set_then_get_round_trips(cache):
    cache.set("topic", {"foo": "bar"}, "Steel")
    got = cache.get("topic", "Steel")
    assert got == {"foo": "bar"}


def test_miss_returns_none(cache):
    assert cache.get("never-cached", "Hospitality") is None


def test_industry_separates_keys(cache):
    cache.set("chiller", {"v": 1}, "Hospitality")
    cache.set("chiller", {"v": 2}, "Pharma")
    assert cache.get("chiller", "Hospitality") == {"v": 1}
    assert cache.get("chiller", "Pharma") == {"v": 2}


def test_no_industry_uses_general_bucket(cache):
    cache.set("topic", {"v": 1})
    assert cache.get("topic") == {"v": 1}
    # Different from explicit industry
    assert cache.get("topic", "Steel") is None


def test_case_insensitive_topic(cache):
    cache.set("Chiller Efficiency", {"v": 1}, "Steel")
    assert cache.get("chiller efficiency", "STEEL") == {"v": 1}


def test_ttl_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(rc_mod, "CACHE_DIR", tmp_path)
    cache = ResearchCache(ttl_days=7)
    cache.set("topic", {"v": 1}, "Steel")

    # Backdate the cache file by 8 days
    f = next(tmp_path.glob("*.json"))
    old_time = time.time() - (8 * 86400)
    os.utime(f, (old_time, old_time))

    assert cache.get("topic", "Steel") is None
