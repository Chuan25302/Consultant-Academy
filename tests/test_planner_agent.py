"""Tests for CalendarPlannerAgent."""
from datetime import datetime
from unittest.mock import MagicMock

from src.agents.planner_agent import CalendarPlannerAgent

SAMPLE_CALENDAR = """
# PTT NGR ESP Consultant Academy
- **2024-05-06**: TECHNICAL | Chiller 101 | Hospitality | chiller,COP | cluster=HVAC | level=1
- **2024-05-07**: INDUSTRY | Hotel Profile | Hospitality | hotel | cluster=Hospitality | level=1
- **2024-05-08**: FRAMEWORK | 5W1H | General | audit | cluster=Audit | level=1
- **2024-05-09**: SOFTSKILL | BANT | General | sales | cluster=Discovery | level=1
- **2024-05-10**: SUSTAINABILITY | Scope 1/2/3 | General | scope,GHG | cluster=GHG | level=1
- **2024-05-11**: RECAP | สรุปสัปดาห์ที่ 1 | General | recap
"""


def _make_agent():
    gemini = MagicMock()
    drive = MagicMock()
    settings = MagicMock()
    settings.CALENDAR_FILE_ID = "fake-calendar-id"
    return CalendarPlannerAgent(gemini, drive, settings)


def _date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def test_needs_extension_when_no_future_topics():
    agent = _make_agent()
    today = _date("2024-12-01")  # well past last entry (2024-05-11)
    assert agent.needs_extension(SAMPLE_CALENDAR, today) is True


def test_needs_extension_false_when_topic_within_window():
    agent = _make_agent()
    today = _date("2024-05-01")  # 5 days before first entry
    # Within 14-day window we should find 2024-05-06
    assert agent.needs_extension(SAMPLE_CALENDAR, today) is False


def test_needs_extension_respects_lookahead_param():
    agent = _make_agent()
    today = _date("2024-04-01")
    # 14-day window misses (2024-05-06 is 35 days out)
    assert agent.needs_extension(SAMPLE_CALENDAR, today, lookahead_days=14) is True
    # 60-day window catches it
    assert agent.needs_extension(SAMPLE_CALENDAR, today, lookahead_days=60) is False


def test_find_last_date_returns_max_date():
    agent = _make_agent()
    last = agent.find_last_date(SAMPLE_CALENDAR)
    assert last == _date("2024-05-11")


def test_find_last_date_returns_none_for_empty_calendar():
    agent = _make_agent()
    assert agent.find_last_date("# empty\n") is None


def test_extract_history_format():
    agent = _make_agent()
    hist = agent.extract_history(SAMPLE_CALENDAR)
    assert "2024-05-06 TECHNICAL: Chiller 101" in hist
    assert "2024-05-10 SUSTAINABILITY: Scope 1/2/3" in hist


def test_extract_history_caps_count():
    agent = _make_agent()
    # Build a calendar with 50 entries
    lines = [
        f"- **2024-{m:02d}-{d:02d}**: TECHNICAL | Topic{m}{d} | X | k | cluster=c | level=1"
        for m in range(1, 13) for d in (1, 15)
    ][:50]
    calendar = "\n".join(lines)
    hist = agent.extract_history(calendar, count=10)
    # Should only return last 10
    assert len(hist.splitlines()) == 10


def test_next_monday():
    agent = _make_agent()
    # Sat 2024-05-11 → next Mon = 2024-05-13
    result = agent._next_monday(_date("2024-05-11"))
    assert result == _date("2024-05-13")
    # Wed 2024-05-08 → next Mon = 2024-05-13
    result = agent._next_monday(_date("2024-05-08"))
    assert result == _date("2024-05-13")
    # Sun 2024-05-12 → next Mon = 2024-05-13
    result = agent._next_monday(_date("2024-05-12"))
    assert result == _date("2024-05-13")


def test_validate_drops_malformed_lines():
    agent = _make_agent()
    raw = """
### Week 5 — Valid
- **2024-06-03**: TECHNICAL | Topic A | X | k | cluster=c | level=1
- this line is garbage
- **2024-06-04**: BOGUSPILLAR | Topic | X | k
- **2024-06-05**: INDUSTRY | Topic B | Y | k | cluster=c | level=1
- **2024-06-06**: COMPLIANCE | Topic C | Z | k | cluster=c | level=2
- **2024-06-07**: SUSTAINABILITY | Topic D | A | k | cluster=c | level=2
- **2024-06-08**: RECAP | สรุป | General | recap
"""
    cleaned = agent._validate(raw, expected_min_lines=4)
    assert cleaned is not None
    assert "BOGUSPILLAR" not in cleaned
    assert "TECHNICAL | Topic A" in cleaned
    assert "INDUSTRY | Topic B" in cleaned
    assert "garbage" not in cleaned


def test_validate_rejects_when_too_few_valid_lines():
    agent = _make_agent()
    raw = "### Week\n- **2024-06-03**: TECHNICAL | only one | X | k\n"
    assert agent._validate(raw, expected_min_lines=4) is None


def test_generate_returns_none_if_no_dates_in_calendar():
    agent = _make_agent()
    out = agent.generate("# empty\n")
    assert out is None


def test_generate_passes_history_and_start_date_to_llm():
    from unittest.mock import patch
    agent = _make_agent()
    fake_output = "\n".join([
        "### Week 5",
        *[
            f"- **2024-05-{13+i:02d}**: TECHNICAL | T{i} | X | k | cluster=c | level=1"
            for i in range(6)
        ],
    ])
    agent.gemini.generate.return_value = fake_output
    # mock today to before calendar's last date so Planner uses last_date path
    with patch("src.agents.planner_agent.now_bangkok",
               return_value=datetime(2024, 5, 1)):
        out = agent.generate(SAMPLE_CALENDAR, num_weeks=1)
    assert out is not None
    args, _ = agent.gemini.generate.call_args
    prompt = args[0]
    assert "2024-05-13" in prompt  # next Monday after 2024-05-11
    assert "Chiller 101" in prompt  # history included


def test_force_extend_writes_to_drive_when_not_dry_run():
    agent = _make_agent()
    fake_output = "\n".join([
        f"- **2024-05-{13+i:02d}**: TECHNICAL | T{i} | X | k | cluster=c | level=1"
        for i in range(6)
    ])
    agent.gemini.generate.return_value = fake_output
    agent.drive.update_file_content.return_value = "ok"

    ok = agent.force_extend(SAMPLE_CALENDAR, num_weeks=1, dry_run=False)
    assert ok is True
    agent.drive.update_file_content.assert_called_once()
    args, kwargs = agent.drive.update_file_content.call_args
    assert "fake-calendar-id" in args
    appended = args[1]
    assert "Chiller 101" in appended  # original kept
    assert "T0" in appended  # new content appended


def test_force_extend_skips_drive_when_dry_run():
    agent = _make_agent()
    fake_output = "\n".join([
        f"- **2024-05-{13+i:02d}**: TECHNICAL | T{i} | X | k | cluster=c | level=1"
        for i in range(6)
    ])
    agent.gemini.generate.return_value = fake_output

    ok = agent.force_extend(SAMPLE_CALENDAR, num_weeks=1, dry_run=True)
    assert ok is True
    agent.drive.update_file_content.assert_not_called()


def test_maybe_extend_skips_when_calendar_has_room():
    agent = _make_agent()
    today = _date("2024-05-01")  # 5 days before first entry
    ok = agent.maybe_extend(SAMPLE_CALENDAR, today=today)
    assert ok is False
    agent.gemini.generate.assert_not_called()


def test_maybe_extend_runs_when_calendar_runs_low():
    agent = _make_agent()
    today = _date("2024-12-01")  # well past last entry
    fake_output = "\n".join([
        f"- **2024-12-{2+i:02d}**: TECHNICAL | T{i} | X | k | cluster=c | level=1"
        for i in range(6)
    ])
    agent.gemini.generate.return_value = fake_output
    agent.drive.update_file_content.return_value = "ok"

    ok = agent.maybe_extend(SAMPLE_CALENDAR, today=today, num_weeks=1)
    assert ok is True
    agent.gemini.generate.assert_called_once()


def test_planner_agent_tag_for_cost_tracking():
    agent = _make_agent()
    fake_output = "\n".join([
        f"- **2024-05-{13+i:02d}**: TECHNICAL | T{i} | X | k | cluster=c | level=1"
        for i in range(6)
    ])
    agent.gemini.generate.return_value = fake_output
    agent.generate(SAMPLE_CALENDAR, num_weeks=1)
    _, kwargs = agent.gemini.generate.call_args
    assert kwargs["agent_tag"] == "planner"
