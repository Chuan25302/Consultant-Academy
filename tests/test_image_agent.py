import logging
from unittest.mock import MagicMock

from src.agents import image_agent
from src.agents.image_agent import ImageAgent, strip_quiz_sections

ARTICLE = """## 💡 ประเด็นวันนี้
เนื้อหาหลักของวันนี้

## 🧰 เครื่องมือ
เครื่องคำนวณ COP

## 🔁 ทวนของเก่า
1. คำถามเกี่ยวกับบทความเก่า

## 🔑 เฉลย
- คำตอบของบทความเก่า
"""


def _agent(model="gemini-3-image"):
    agent = ImageAgent.__new__(ImageAgent)
    agent.model_name = model
    agent.client = MagicMock()
    return agent


def _response(finish_reason=None, text=None, image=None, block_reason=None):
    part = MagicMock()
    part.inline_data = None
    part.text = text
    if image is not None:
        part.inline_data = MagicMock(mime_type="image/png", data=image)
    cand = MagicMock()
    cand.finish_reason = finish_reason
    cand.content.parts = [part]
    resp = MagicMock()
    resp.candidates = [cand]
    resp.prompt_feedback = (
        MagicMock(block_reason=block_reason) if block_reason else None
    )
    return resp


def test_strip_removes_both_sections_keeps_rest():
    out = strip_quiz_sections(ARTICLE)
    assert "ทวนของเก่า" not in out and "เฉลย" not in out
    assert "คำถามเกี่ยวกับบทความเก่า" not in out
    assert "คำตอบของบทความเก่า" not in out
    assert "## 🧰 เครื่องมือ" in out and "เครื่องคำนวณ COP" in out
    assert "เนื้อหาหลักของวันนี้" in out


def test_strip_stops_at_next_heading():
    md = "## 🔁 ทวนของเก่า\nq\n## 📖 ศัพท์\nคำศัพท์\n"
    out = strip_quiz_sections(md)
    assert "q" not in out.replace("คำศัพท์", "") and "## 📖 ศัพท์" in out


def test_strip_is_noop_without_recall_block():
    old = "## 💡 ประเด็นวันนี้\nเนื้อหา\n\n## 🧰 เครื่องมือ\nkit\n"
    assert strip_quiz_sections(old) == old


def test_strip_happens_before_cap():
    agent = _agent()
    agent._call_gemini_image = MagicMock(return_value=b"png")
    # Real content ends at ~5500 chars; the quiz would push it past 6000.
    body = "## 💡 ประเด็น\n" + ("ก" * 5500) + "\nTAIL_MARKER\n"
    quiz = "## 🔁 ทวนของเก่า\n" + ("ข" * 1000) + "\n## 🔑 เฉลย\n" + ("ค" * 1000)
    agent.generate(body + quiz, {})
    prompt = agent._call_gemini_image.call_args[0][0]
    assert "TAIL_MARKER" in prompt
    assert "ข" * 10 not in prompt and "ค" * 10 not in prompt


def test_empty_twice_retries_exactly_once_and_returns_none():
    agent = _agent()
    agent._call_gemini_image = MagicMock(return_value=None)
    assert agent.generate(ARTICLE, {}) is None
    assert agent._call_gemini_image.call_count == 2


def test_retry_success_returns_bytes():
    agent = _agent()
    agent._call_gemini_image = MagicMock(side_effect=[None, b"png-bytes"])
    assert agent.generate(ARTICLE, {}) == b"png-bytes"
    assert agent._call_gemini_image.call_count == 2


def test_no_retry_when_first_call_succeeds():
    agent = _agent()
    agent._call_gemini_image = MagicMock(return_value=b"x")
    agent.generate(ARTICLE, {})
    assert agent._call_gemini_image.call_count == 1


def test_exception_still_returns_none():
    agent = _agent()
    agent._call_gemini_image = MagicMock(side_effect=RuntimeError("boom"))
    assert agent.generate(ARTICLE, {}) is None


def test_diagnostic_log_has_finish_reason_and_text(caplog):
    agent = _agent()
    agent.client.models.generate_content.return_value = _response(
        finish_reason="STOP", text="I cannot draw this because " + "x" * 400,
        block_reason="SAFETY",
    )
    with caplog.at_level(logging.INFO, logger=image_agent.logger.name):
        assert agent._call_gemini_image("p") is None
    msgs = [r.getMessage() for r in caplog.records if "🎨" in r.getMessage()]
    joined = "\n".join(msgs)
    assert "STOP" in joined
    assert "SAFETY" in joined
    assert "I cannot draw this because" in joined
    assert "x" * 300 not in joined  # text truncated to ~200 chars


def test_diagnostic_log_survives_missing_attributes(caplog):
    agent = _agent()
    agent.client.models.generate_content.return_value = object()
    with caplog.at_level(logging.INFO, logger=image_agent.logger.name):
        assert agent._call_gemini_image("p") is None


def test_strip_survives_paraphrased_headings():
    md = (
        "## 💡 ประเด็น\nหลัก\n\n## 🧰 เครื่องมือ\nkit\n\n"
        "## 🔁 ทวนความรู้เก่า\n- q1\n\n## 🔑 เฉลยคำถาม\n- a1\n\n"
        "## 📖 ศัพท์\n- t\n"
    )
    out = strip_quiz_sections(md)
    assert "q1" not in out and "a1" not in out
    assert "🔁" not in out and "🔑" not in out
    assert "## 🧰 เครื่องมือ" in out and "## 📖 ศัพท์" in out and "- t" in out
