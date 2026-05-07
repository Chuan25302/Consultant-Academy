"""Tests for Settings.model_for() — per-agent model resolution."""
from src.config.settings import Settings


def test_default_when_no_overrides(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL_EXPERT", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert Settings.model_for("expert") == Settings.GEMINI_MODEL


def test_global_env_overrides_class_default(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL_EXPERT", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    assert Settings.model_for("expert") == "gemini-2.5-flash"


def test_per_agent_override_wins(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setenv("GEMINI_MODEL_EXPERT", "gemini-2.5-pro")
    assert Settings.model_for("expert") == "gemini-2.5-pro"
    # other agents still use global default
    monkeypatch.delenv("GEMINI_MODEL_RESEARCH", raising=False)
    assert Settings.model_for("research") == "gemini-2.0-flash"


def test_agent_tag_case_insensitive(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_EXPERT", "gemini-2.5-pro")
    assert Settings.model_for("expert") == "gemini-2.5-pro"
    assert Settings.model_for("EXPERT") == "gemini-2.5-pro"
    assert Settings.model_for("Expert") == "gemini-2.5-pro"


def test_unknown_agent_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL_BOGUS", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert Settings.model_for("bogus") == Settings.GEMINI_MODEL
