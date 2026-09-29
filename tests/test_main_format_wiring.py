# tests/test_main_format_wiring.py
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src import main as main_mod

BKK = ZoneInfo("Asia/Bangkok")
CALENDAR = (
    "- **2026-05-04**: TECHNICAL | Chiller 101 | Hospitality | chiller "
    "| cluster=HVAC | level=3\n"
)


@pytest.fixture
def deps():
    drive, gemini = MagicMock(), MagicMock()
    patches = [
        patch.object(main_mod, "DriveAPI", return_value=drive),
        patch.object(main_mod, "GeminiClient", return_value=gemini),
        patch.object(main_mod, "ResearchCache"),
        patch.object(main_mod, "validate_startup"),
        patch.object(main_mod, "ResearchAgent"),
        patch.object(main_mod, "ExpertAgent"),
        patch.object(main_mod, "IndustryAgent"),
        patch.object(main_mod, "FactCheckerAgent"),
        patch.object(main_mod, "TranslatorAgent"),
        patch.object(main_mod, "EditorAgent"),
        patch.object(main_mod, "DesignerAgent"),
        patch.object(main_mod, "ImageAgent"),
        patch.object(main_mod, "IndexBuilder"),
        patch.object(main_mod, "CalendarPlannerAgent"),
        patch.object(main_mod, "send_daily_email", return_value=True),
        patch.object(main_mod, "markdown_to_docx_bytes", return_value=b"d"),
    ]
    for p in patches:
        p.start()
    drive.download_file.return_value = CALENDAR
    yield drive
    for p in patches:
        p.stop()


def _run():
    with patch.object(main_mod, "now_bangkok",
                      return_value=datetime(2026, 5, 4, 8, 0, tzinfo=BKK)):
        return main_mod.main(skip_validation=True, dry_run=True)


def test_translator_receives_level_industry_and_a_scene(deps):
    _run()
    kwargs = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs
    assert kwargs["level"] == 3
    assert kwargs["industry"] == "Hospitality"
    assert kwargs["scene"], "a scene must always be assigned"


def test_recall_items_come_from_the_index(deps):
    main_mod.IndexBuilder.return_value.recall_candidates.return_value = [
        {"title": "Pump curves", "date": "2026-04-28", "tldr": "x"}]
    _run()
    kwargs = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs
    assert kwargs["recall_items"][0]["title"] == "Pump curves"


def test_recall_failure_does_not_stop_the_run(deps):
    main_mod.IndexBuilder.return_value.recall_candidates.side_effect = \
        RuntimeError("drive down")
    result = _run()
    assert result["status"] == "success"
    kwargs = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs
    assert kwargs["recall_items"] == []


def test_editor_is_told_which_kit_and_scene_to_enforce(deps):
    _run()
    kwargs = main_mod.EditorAgent.return_value.review.call_args.kwargs
    assert kwargs["kit"] == "checklist"   # TECHNICAL profile
    assert kwargs["scene"]


def test_editor_is_told_whether_recall_was_requested(deps):
    main_mod.IndexBuilder.return_value.recall_candidates.return_value = []
    _run()
    assert main_mod.EditorAgent.return_value.review.call_args.kwargs["recall"] is False
    main_mod.IndexBuilder.return_value.recall_candidates.return_value = [
        {"title": "Pump curves", "date": "2026-04-28", "tldr": "x"}]
    _run()
    assert main_mod.EditorAgent.return_value.review.call_args.kwargs["recall"] is True


def test_index_builder_is_constructed_once(deps):
    main_mod.IndexBuilder.reset_mock()
    _run()
    assert main_mod.IndexBuilder.call_count == 1


def test_recent_scenes_exclude_the_date_being_generated(deps):
    _run()
    kwargs = main_mod.IndexBuilder.return_value.recent_scenes.call_args.kwargs
    assert kwargs["exclude_date"] == "2026-05-04"


def test_recent_scenes_feed_scene_for(deps):
    with patch.object(main_mod, "scene_for", return_value="S") as sf:
        main_mod.IndexBuilder.return_value.recent_scenes.return_value = [
            {"scene": "A"}, {"scene": "B"}]
        _run()
    assert sf.call_args.kwargs["recent"] == ["A", "B"]


def test_recent_scenes_failure_means_no_constraint(deps):
    main_mod.IndexBuilder.return_value.recent_scenes.side_effect = RuntimeError("x")
    with patch.object(main_mod, "scene_for", return_value="S") as sf:
        result = _run()
    assert result["status"] == "success"
    assert sf.call_args.kwargs["recent"] == []


def test_non_dry_run_persists_scene_and_date_in_the_summary(deps):
    deps.upload.return_value = "id1"
    with patch.object(main_mod, "now_bangkok",
                      return_value=datetime(2026, 5, 4, 8, 0, tzinfo=BKK)):
        main_mod.main(skip_validation=True, dry_run=False)
    scene = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs["scene"]
    call = main_mod.IndexBuilder.return_value.update_summary.call_args
    assert call.kwargs == {"scene": scene, "date": "2026-05-04"}
