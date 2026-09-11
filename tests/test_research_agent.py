from unittest.mock import MagicMock

from src.agents.research_agent import ResearchAgent


def test_failed_research_is_not_cached():
    # generate_json returns {} when Gemini errors. Caching the fallback
    # skeleton would serve empty research for this topic for 7 days,
    # even after Gemini recovers and the run is retried.
    gemini = MagicMock()
    gemini.generate_json.return_value = {}
    cache = MagicMock()
    cache.get.return_value = None

    data = ResearchAgent(gemini, cache).gather("Chiller 101", "Hospitality")

    assert data["case_studies"] == []  # skeleton still returned
    cache.set.assert_not_called()


def test_real_research_is_cached():
    gemini = MagicMock()
    gemini.generate_json.return_value = {"case_studies": ["x"]}
    cache = MagicMock()
    cache.get.return_value = None

    ResearchAgent(gemini, cache).gather("Chiller 101", "Hospitality")

    cache.set.assert_called_once()
