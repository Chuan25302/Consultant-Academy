"""Tests for skill_loader — file-based card matching."""
from pathlib import Path

import pytest

import src.utils.skill_loader as sl_mod
from src.utils.skill_loader import _score, _terms_from_topic, load_skills


@pytest.fixture
def fake_skills_dir(tmp_path, monkeypatch):
    """Build a small fake skills tree to test loader logic in isolation."""
    (tmp_path / "equipment").mkdir()
    (tmp_path / "industries").mkdir()
    (tmp_path / "frameworks").mkdir()

    (tmp_path / "equipment" / "chiller.md").write_text("# Chiller\n", encoding="utf-8")
    (tmp_path / "equipment" / "motor.md").write_text("# Motor\n", encoding="utf-8")
    (tmp_path / "equipment" / "pump.md").write_text("# Pump\n", encoding="utf-8")
    (tmp_path / "industries" / "automotive-oem.md").write_text("# Auto OEM\n", encoding="utf-8")
    (tmp_path / "industries" / "hospitals.md").write_text("# Hospitals\n", encoding="utf-8")
    (tmp_path / "frameworks" / "bant.md").write_text("# BANT\n", encoding="utf-8")

    monkeypatch.setattr(sl_mod, "SKILLS_DIR", tmp_path)
    return tmp_path


def test_terms_from_topic_collects_all_searchable_fields():
    topic = {
        "topic": "Chiller Efficiency 101",
        "industry": "Hospitality",
        "cluster": "HVAC-Chillers",
        "keywords": ["chiller", "COP", "fouling"],
    }
    terms = _terms_from_topic(topic)
    assert "chiller" in terms
    assert "cop" in terms  # lowercased
    assert "hvac-chillers" in terms
    assert "hospitality" in terms


def test_terms_handles_missing_fields():
    assert _terms_from_topic({}) == set()
    assert _terms_from_topic({"topic": ""}) == set()


def test_score_matches_filename_words():
    assert _score("chiller.md", {"chiller", "cop"}) > 0
    assert _score("motor.md", {"chiller"}) == 0
    # Partial / substring match
    assert _score("automotive-oem.md", {"automotive"}) > 0


def test_load_skills_picks_relevant_card(fake_skills_dir):
    topic = {"topic": "Chiller Efficiency", "keywords": ["chiller"], "cluster": "HVAC"}
    out = load_skills(topic)
    assert "Chiller" in out
    assert "Motor" not in out
    assert "Pump" not in out


def test_load_skills_caps_at_max_cards(fake_skills_dir):
    topic = {
        "topic": "all",
        "keywords": ["chiller", "motor", "pump", "automotive", "bant"],
    }
    out = load_skills(topic, max_cards=3)
    assert "SKILL CARDS" in out
    # Verify no more than 3 distinct card filenames represented
    cards = sum(1 for name in ["Chiller", "Motor", "Pump", "Auto OEM", "BANT"]
                if name in out)
    assert cards <= 3


def test_load_skills_returns_empty_for_no_match(fake_skills_dir):
    topic = {"topic": "underwater basket weaving", "keywords": ["basket"]}
    assert load_skills(topic) == ""


def test_load_skills_returns_empty_for_empty_topic(fake_skills_dir):
    assert load_skills({}) == ""
    assert load_skills({"topic": ""}) == ""


def test_load_skills_handles_missing_skills_dir(tmp_path, monkeypatch):
    nonexistent = tmp_path / "does-not-exist"
    monkeypatch.setattr(sl_mod, "SKILLS_DIR", nonexistent)
    assert load_skills({"keywords": ["x"]}) == ""


def test_real_skills_dir_loads_chiller_card():
    """Sanity check: real src/skills/ has the chiller card we wrote."""
    real_dir = Path(__file__).parent.parent / "src" / "skills"
    assert real_dir.exists()
    assert (real_dir / "equipment" / "chiller.md").exists()
    assert (real_dir / "industries" / "automotive-oem.md").exists()
    assert (real_dir / "frameworks" / "bant.md").exists()
    # Stage 3 additions
    assert (real_dir / "equipment" / "boiler.md").exists()
    assert (real_dir / "equipment" / "solar-pv.md").exists()
    assert (real_dir / "standards" / "iso-50001.md").exists()
    assert (real_dir / "standards" / "ipmvp.md").exists()


def test_real_topic_pulls_iso_50001_card():
    """Compliance topic about ISO 50001 should match the standards card."""
    topic = {
        "topic": "ISO 50001 Implementation Roadmap",
        "industry": "General",
        "cluster": "ISO-50001",
        "keywords": ["ISO 50001", "EnMS"],
    }
    out = load_skills(topic)
    assert "ISO 50001" in out
    assert "EnMS" in out or "PDCA" in out  # from the card


def test_real_topic_pulls_relevant_real_card():
    """End-to-end with the actual src/skills/ contents."""
    topic = {
        "topic": "Chiller Efficiency 101",
        "industry": "Hospitality",
        "cluster": "HVAC-Chillers",
        "keywords": ["chiller", "COP", "fouling"],
    }
    out = load_skills(topic)
    assert "Chiller" in out
    assert "TIS 2854" in out  # from the real card
