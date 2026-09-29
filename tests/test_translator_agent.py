import re

import pytest

from src.agents.formats import FORMAT_PROFILES, KIT_SPECS, REFERENCE_FIGURES
from src.agents.translator_agent import TranslatorAgent, build_prompt


class _CapturingGemini:
    def __init__(self):
        self.prompt = ""

    def generate(self, prompt, max_tokens=None, agent_tag="unknown"):
        self.prompt = prompt
        return "## 💡 ประเด็นวันนี้\nok"


def test_translator_sees_the_whole_fact_checked_draft():
    # The FactChecker's verified draft is the grounded source for the
    # Case Study numbers. Truncating it (was [:1500]) forced the model to
    # invent figures for everything past the cut.
    tail_marker = "TAIL-FACT-42 kWh"
    verified = ("ข้อเท็จจริงที่ผ่านการตรวจแล้ว " * 200) + tail_marker  # ~6k chars
    g = _CapturingGemini()
    TranslatorAgent(g).simplify(verified, None, "Topic", "TECHNICAL")
    assert tail_marker in g.prompt


ANCHOR_RES = [
    re.compile(r"^## 💡 ประเด็นวันนี้$", re.M),
    re.compile(r"^## (?:\d+\. )?Consultant Move$", re.M),
    re.compile(r"^## (?:\d+\. )?Knowledge Capture$", re.M),
    re.compile(r"^## 📖 ศัพท์น่ารู้$", re.M),
]


def _prompt(pillar="TECHNICAL", **kw):
    args = dict(topic="Chiller COP", pillar=pillar, level=2,
                industry="Hospitality", expert_content="ข้อเท็จจริงที่ตรวจแล้ว",
                scene="โรงแรมริมทะเล", recall_items=())
    args.update(kw)
    return build_prompt(**args)


@pytest.mark.parametrize("pillar", list(FORMAT_PROFILES))
def test_every_pillar_prompt_keeps_all_four_anchors(pillar):
    p = _prompt(pillar)
    for rx in ANCHOR_RES:
        assert rx.search(p), f"{pillar} lost anchor {rx.pattern}"


@pytest.mark.parametrize("pillar", list(FORMAT_PROFILES))
def test_prompt_carries_that_pillars_sections_and_kit(pillar):
    p = _prompt(pillar)
    for title, _ in FORMAT_PROFILES[pillar].sections:
        assert title in p
    assert KIT_SPECS[FORMAT_PROFILES[pillar].kit].label in p


def test_prompt_states_one_mental_model_and_the_level():
    p = _prompt(level=3)
    assert "หลักคิดวันนี้" in p
    assert "L3" in p


def test_prompt_pins_the_assigned_scene():
    assert "โรงแรมริมทะเล" in _prompt()


def test_recall_block_appears_only_when_items_are_supplied():
    without = _prompt()
    assert "🔁 ทวนของเก่า" not in without
    assert "🔑 เฉลย" not in without
    p = _prompt(recall_items=[
        {"title": "Pump curves", "date": "2026-10-10",
         "tldr": "เลือกปั๊มต้องดูจุดทำงานจริง"}])
    q, a = p.index("🔁 ทวนของเก่า"), p.index("🔑 เฉลย")
    assert q < a
    assert q < p.index("Pump curves") < a


def test_length_targets_match_the_amended_spec():
    p = _prompt()
    assert "600–700 คำ" in p


def test_simplify_passes_the_whole_fact_checked_draft():
    tail = "TAIL-FACT-42 kWh"
    g = _CapturingGemini()
    TranslatorAgent(g).simplify(("ข้อเท็จจริง " * 200) + tail, None,
                                "Topic", "TECHNICAL", level=1,
                                industry="Food", scene="โรงงานกระดาษ")
    assert tail in g.prompt


def test_scene_rule_only_present_when_a_scene_is_given():
    assert "ห้ามเปลี่ยนไปใช้ฉากอื่น" not in _prompt(scene="")
    assert "****" not in _prompt(scene="")
    assert "ห้ามเปลี่ยนไปใช้ฉากอื่น" in _prompt(scene="โรงแรมริมทะเล")


def test_calculator_pillars_receive_the_reference_table():
    assert REFERENCE_FIGURES.strip() in _prompt("SUSTAINABILITY")
    assert REFERENCE_FIGURES.strip() in _prompt("FRAMEWORK")


@pytest.mark.parametrize("pillar", ["TECHNICAL", "INDUSTRY", "COMPLIANCE", "SOFTSKILL"])
def test_non_calculator_pillars_do_not_carry_it(pillar):
    assert "ค่าไฟเฉลี่ยภาคอุตสาหกรรม" not in _prompt(pillar)
    assert REFERENCE_FIGURES.strip() not in _prompt(pillar)


def test_reference_block_is_labelled_input_before_output_skeleton():
    p = _prompt("SUSTAINABILITY")
    assert p.index("input เท่านั้น") < p.index(REFERENCE_FIGURES.strip()) < p.index("## 🧰")
