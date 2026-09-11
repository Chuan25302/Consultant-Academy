from pathlib import Path
from unittest.mock import patch

from src import notify_failure

# Real tail of a failed run (expert stage, Vertex 404), project id redacted.
REAL_LOG = Path(__file__).parent / "fixtures" / "failed_run_expert_404.log"
RUN_URL = "https://github.com/Chuan25302/Consultant-Academy/actions/runs/1"


def test_alert_names_the_failing_stage_and_links_the_run():
    subject, body = notify_failure.build_alert(
        REAL_LOG.read_text(encoding="utf-8"), RUN_URL)
    assert "LLMStageError: expert" in body
    assert RUN_URL in body
    assert "ไม่ได้ส่ง" in subject or "ล้มเหลว" in subject


def test_alert_without_a_log_still_links_the_run():
    _, body = notify_failure.build_alert("", RUN_URL)
    assert RUN_URL in body


def test_sends_only_to_alert_email(monkeypatch, tmp_path):
    log = tmp_path / "run.log"
    log.write_text(REAL_LOG.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("ALERT_EMAIL", "owner@example.com")
    monkeypatch.setenv("RUN_URL", RUN_URL)
    with patch.object(notify_failure, "send_daily_email", return_value=True) as send:
        notify_failure.main(str(log))
    assert send.call_args.kwargs["recipients"] == ["owner@example.com"]


def test_no_alert_email_configured_is_a_quiet_no_op(monkeypatch, tmp_path):
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    with patch.object(notify_failure, "send_daily_email") as send:
        assert notify_failure.main(str(tmp_path / "missing.log")) == 0
    send.assert_not_called()
