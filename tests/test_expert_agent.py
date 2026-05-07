"""Tests for ExpertAgent — pillar-aware prompt selection."""
from unittest.mock import MagicMock

from src.agents.expert_agent import (
    COMPLIANCE_PROMPT,
    FRAMEWORK_PROMPT,
    INDUSTRY_PROMPT,
    PROMPTS,
    SOFTSKILL_PROMPT,
    SUSTAINABILITY_PROMPT,
    TECHNICAL_PROMPT,
    ExpertAgent,
)


def test_all_pillars_have_prompts():
    expected = {"TECHNICAL", "INDUSTRY", "FRAMEWORK", "SOFTSKILL",
                "COMPLIANCE", "SUSTAINABILITY"}
    assert expected.issubset(PROMPTS.keys())


def test_sustainability_prompt_lists_thai_carbon_programs():
    assert "TGO" in SUSTAINABILITY_PROMPT
    assert "T-VER" in SUSTAINABILITY_PROMPT
    assert "CBAM" in SUSTAINABILITY_PROMPT
    assert "Net Zero" in SUSTAINABILITY_PROMPT or "net zero" in SUSTAINABILITY_PROMPT.lower()


def test_sustainability_prompt_lists_iso_standards():
    assert "ISO 14064" in SUSTAINABILITY_PROMPT
    assert "ISO 14067" in SUSTAINABILITY_PROMPT
    assert "GHG Protocol" in SUSTAINABILITY_PROMPT


def test_sustainability_prompt_has_anti_hallucination():
    # Carbon math is the easiest place to fabricate — must have guard
    assert "ห้าม" in SUSTAINABILITY_PROMPT


def test_compliance_prompt_lists_expanded_standards():
    """Standards expansion: should mention key Thai + international additions."""
    standards = [
        "ISO 14064", "ISO 14067", "ISO 50002", "IPMVP",
        "IATF 16949", "IPC", "ASME", "ASHRAE 90.1",
        "WHO GMP", "BRCGS", "FSSC 22000",
        "TIS 2780", "กรอ.4", "ม.32", "BEC",
    ]
    missing = [s for s in standards if s not in COMPLIANCE_PROMPT]
    assert not missing, f"missing from COMPLIANCE_PROMPT: {missing}"


def test_softskill_prompt_requires_named_framework():
    assert "framework" in SOFTSKILL_PROMPT.lower()
    assert "BANT" in SOFTSKILL_PROMPT
    assert "MEDDIC" in SOFTSKILL_PROMPT
    assert "SPIN" in SOFTSKILL_PROMPT


def test_compliance_prompt_lists_real_standards():
    assert "ISO 50001" in COMPLIANCE_PROMPT
    assert "GMP" in COMPLIANCE_PROMPT
    assert "HACCP" in COMPLIANCE_PROMPT
    assert "พ.ร.บ. ส่งเสริมการอนุรักษ์พลังงาน 2535" in COMPLIANCE_PROMPT
    assert "มอก." in COMPLIANCE_PROMPT or "TIS" in COMPLIANCE_PROMPT


def test_compliance_prompt_has_anti_hallucination():
    # COMPLIANCE is the riskiest pillar for hallucination — must include guard
    assert "ห้าม" in COMPLIANCE_PROMPT


def test_technical_prompt_lists_equipment():
    # Embedded equipment primer should mention the major families
    rendered = TECHNICAL_PROMPT  # template references equipment via {equipment}
    # The actual equipment text is injected by ExpertAgent at draft time;
    # we verify the placeholder exists.
    assert "{equipment}" in rendered


def test_draft_picks_prompt_by_pillar(monkeypatch):
    gemini = MagicMock()
    gemini.generate.return_value = "OK"
    agent = ExpertAgent(gemini)

    agent.draft("test", "COMPLIANCE", {}, industry="Pharma")
    args, kwargs = gemini.generate.call_args
    prompt = args[0] if args else kwargs.get("prompt", "")
    # Compliance prompt distinct marker
    assert "ภาพรวมมาตรฐาน" in prompt or "Compliance" in prompt


def test_draft_falls_back_to_technical_for_unknown_pillar():
    gemini = MagicMock()
    gemini.generate.return_value = "OK"
    agent = ExpertAgent(gemini)

    agent.draft("test", "BOGUS_PILLAR", {}, industry="X")
    args, _ = gemini.generate.call_args
    prompt = args[0]
    # Technical structure markers
    assert "วิธีวิเคราะห์" in prompt or "ตัวเลือกแก้ไข" in prompt


def test_draft_passes_agent_tag():
    gemini = MagicMock()
    gemini.generate.return_value = "OK"
    ExpertAgent(gemini).draft("t", "TECHNICAL", {}, industry="Hospitality")
    _, kwargs = gemini.generate.call_args
    assert kwargs["agent_tag"] == "expert"


def test_industry_prompt_mentions_thai_context():
    assert "ไทย" in INDUSTRY_PROMPT or "Thai" in INDUSTRY_PROMPT


def test_framework_prompt_emphasizes_real_provenance():
    # Framework prompt must remind not to invent framework origins
    assert "ห้าม" in FRAMEWORK_PROMPT
