"""
Tests for main.py self-healing behavior when calendar has no topic for the
target date. Covers:
  - Saturday → RECAP fallback (no LLM cost, runs RecapAgent)
  - Weekday → triggers planner force_extend, reloads, and retries
  - Weekday → still fails after extend → returns no_topic error
"""
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src import main as main_mod

BKK = ZoneInfo("Asia/Bangkok")

CALENDAR_WITH_WEEK = """
- **2026-05-04**: TECHNICAL | Chiller 101 | Hospitality | chiller | cluster=HVAC | level=1
- **2026-05-05**: INDUSTRY | Hotel Profile | Hospitality | hotel | cluster=Hospitality | level=1
- **2026-05-06**: FRAMEWORK | 5W1H | General | audit | cluster=Audit | level=1
- **2026-05-07**: SOFTSKILL | BANT | General | sales | cluster=Discovery | level=1
- **2026-05-08**: SUSTAINABILITY | Scope 1/2/3 | General | scope | cluster=GHG | level=1
"""

CALENDAR_AFTER_EXTEND = CALENDAR_WITH_WEEK + """
- **2026-05-11**: TECHNICAL | Pump basics | General | pump | cluster=Pump | level=1
"""


@pytest.fixture
def mocked_main_deps():
    """Patch all heavy dependencies in main.py so we can drive the flow."""
    drive = MagicMock()
    gemini = MagicMock()

    patches = [
        patch.object(main_mod, "DriveAPI", return_value=drive),
        patch.object(main_mod, "GeminiClient", return_value=gemini),
        patch.object(main_mod, "ResearchCache"),
        patch.object(main_mod, "validate_startup"),
        patch.object(main_mod, "RecapAgent"),
        patch.object(main_mod, "ResearchAgent"),
        patch.object(main_mod, "ExpertAgent"),
        patch.object(main_mod, "IndustryAgent"),
        patch.object(main_mod, "FactCheckerAgent"),
        patch.object(main_mod, "TranslatorAgent"),
        patch.object(main_mod, "EditorAgent"),
        patch.object(main_mod, "DesignerAgent"),
        patch.object(main_mod, "IndexBuilder"),
        patch.object(main_mod, "CalendarPlannerAgent"),
        patch.object(main_mod, "send_daily_email", return_value=True),
        patch.object(main_mod, "markdown_to_docx_bytes", return_value=b"docx"),
    ]
    for p in patches:
        p.start()
    yield {
        "drive": drive,
        "gemini": gemini,
        "RecapAgent": main_mod.RecapAgent,
        "CalendarPlannerAgent": main_mod.CalendarPlannerAgent,
    }
    for p in patches:
        p.stop()


def test_saturday_no_topic_falls_back_to_recap(mocked_main_deps):
    """Saturday with missing topic should run RECAP, not error out."""
    deps = mocked_main_deps
    deps["drive"].download_file.return_value = CALENDAR_WITH_WEEK

    saturday = datetime(2026, 5, 9, 8, 0, tzinfo=BKK)
    with patch.object(main_mod, "now_bangkok", return_value=saturday):
        result = main_mod.main(skip_validation=True, dry_run=True)

    assert result["status"] == "success"
    assert result["pillar"] == "RECAP"
    deps["RecapAgent"].assert_called()
    deps["RecapAgent"].return_value.generate_and_upload.assert_called()
    # Planner should NOT be invoked on Saturday fallback
    deps["CalendarPlannerAgent"].assert_not_called()


def test_weekday_no_topic_triggers_force_extend_then_succeeds(mocked_main_deps):
    """Weekday miss → planner extends → reload finds topic → pipeline runs."""
    deps = mocked_main_deps
    # First read: no topic for 2026-05-11. After extend: contains 2026-05-11.
    deps["drive"].download_file.side_effect = [
        CALENDAR_WITH_WEEK,           # initial read
        CALENDAR_AFTER_EXTEND,        # reload after force_extend
    ]
    planner_instance = MagicMock()
    planner_instance.force_extend.return_value = True
    planner_instance.maybe_extend.return_value = False
    deps["CalendarPlannerAgent"].return_value = planner_instance

    monday = datetime(2026, 5, 11, 8, 0, tzinfo=BKK)
    with patch.object(main_mod, "now_bangkok", return_value=monday):
        # dry_run=False so the auto-extend branch fires; agents are mocked
        # so no real Drive uploads happen.
        result = main_mod.main(skip_validation=True, dry_run=False)

    assert result["status"] == "success"
    assert result["pillar"] == "TECHNICAL"
    assert result["topic"] == "Pump basics"
    planner_instance.force_extend.assert_called_once()


def test_weekday_no_topic_extend_fails_returns_error(mocked_main_deps):
    """If planner can't extend, we return a clean no_topic error."""
    deps = mocked_main_deps
    deps["drive"].download_file.return_value = CALENDAR_WITH_WEEK
    planner_instance = MagicMock()
    planner_instance.force_extend.return_value = False
    deps["CalendarPlannerAgent"].return_value = planner_instance

    monday = datetime(2026, 5, 11, 8, 0, tzinfo=BKK)
    with patch.object(main_mod, "now_bangkok", return_value=monday):
        result = main_mod.main(skip_validation=True, dry_run=False)

    assert result["status"] == "error"
    assert result["reason"] == "no_topic"
    planner_instance.force_extend.assert_called_once()


def test_dry_run_weekday_skips_force_extend(mocked_main_deps):
    """In dry_run we don't want to mutate Drive — skip auto-extend, return error."""
    deps = mocked_main_deps
    deps["drive"].download_file.return_value = CALENDAR_WITH_WEEK
    planner_instance = MagicMock()
    deps["CalendarPlannerAgent"].return_value = planner_instance

    monday = datetime(2026, 5, 11, 8, 0, tzinfo=BKK)
    with patch.object(main_mod, "now_bangkok", return_value=monday):
        result = main_mod.main(skip_validation=True, dry_run=True)

    assert result["status"] == "error"
    assert result["reason"] == "no_topic"
    planner_instance.force_extend.assert_not_called()
