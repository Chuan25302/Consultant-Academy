import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.editor_agent import (
    MAX_THAI_CHARS,
    NUMBER_WITH_UNIT_RE,
    THAI_CHAR_RE,
    EditorAgent,
)

GOOD = """## 💡 ประเด็นวันนี้
ลูกค้าไม่ต้องการ chiller ใหม่ แต่ต้องการลดค่าไฟที่วัดผลได้

**หลักคิดวันนี้:** วัด COP ก่อนเสนอ solution

## 1. หน้างานบอกอะไร
โรงแรม 200 ห้อง ค่าไฟเดือนละ 250000 บาท chiller ทำงาน 800 kW

## 2. เคสสั้น: จากอาการสู่ทางแก้
วิเคราะห์ COP จริงด้วย data logger ลด COP loss ได้ 25% คืนทุนภายใน 3 ปี

## 3. Consultant Move
ถามลูกค้าเรื่อง baseline

## 4. Knowledge Capture
วัดก่อนเสนอ

## 📖 ศัพท์น่ารู้
- COP = ค่าประสิทธิภาพ
- Fouling = คราบสะสม
"""


def test_check_passes_full_article():
    assert EditorAgent.check(GOOD) == []


@pytest.mark.parametrize("anchor", ["💡 ประเด็นวันนี้", "Consultant Move",
                                    "Knowledge Capture", "📖 ศัพท์น่ารู้"])
def test_check_flags_each_missing_anchor(anchor):
    md = GOOD.replace(anchor, "หัวข้ออื่น")
    assert any(anchor in i for i in EditorAgent.check(md))


def test_lead_anchor_must_be_a_heading():
    md = GOOD.replace("## 💡 ประเด็นวันนี้", "พูดถึง 💡 ประเด็นวันนี้ ในประโยค")
    assert any("💡" in i for i in EditorAgent.check(md))


def test_check_flags_too_few_numbers():
    md = "## หัว\nเนื้อหาไม่มีตัวเลข\n\n## Consultant Move\nถามลูกค้า\n\n📖 ศัพท์น่ารู้: A=B"
    issues = EditorAgent.check(md)
    assert any("ตัวเลขจริง" in i for i in issues)


def test_check_recognizes_thai_units():
    md = "ค่าไฟ 250000 บาท ใช้ไฟ 800 kWh ลด 25% ROI 2 ปี"
    md += "\n\n## Consultant Move\nถาม\n\n📖 ศัพท์น่ารู้: A=B"
    issues = EditorAgent.check(md)
    assert not any("ตัวเลข" in i for i in issues)


def test_check_flags_overlong_thai_content():
    """A5: the gate measures Thai CHARACTERS. Thai has no spaces, so the old
    word-count ceiling (1,200 words) could never fire on a Thai draft."""
    long_md = GOOD + "\nวิธีลดต้นทุนพลังงานในโรงงานอย่างเป็นระบบ " * 200
    assert len(long_md.split()) < 1200  # a word count still would not fire
    assert any("ยาว" in i for i in EditorAgent.check(long_md))


def test_a_normal_length_thai_article_does_not_trip_the_gate():
    """~5,800 Thai characters — above the longest real sample of the
    2026-09-29 dry run (5,464) and still below the ceiling."""
    md = GOOD + "\nวิธีลดต้นทุนพลังงานในโรงงานอย่างเป็นระบบ " * 150
    assert 5500 < len(THAI_CHAR_RE.findall(md)) < MAX_THAI_CHARS
    assert not any("ยาว" in i for i in EditorAgent.check(md))


def test_ceiling_sits_above_a_real_dry_run_article():
    """Guard the constant against a future 'tidy-up' that lowers it under the
    real content. Body text of a captured 2026-10-05 TECHNICAL email
    (tests/fixtures/, six-pillar dry run 2026-09-29)."""
    html = (Path(__file__).parent / "fixtures"
            / "email_archive_2026-10-05_TECHNICAL.html").read_text(encoding="utf-8")
    body = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", " ", html, flags=re.S)
    body = re.sub(r'<div class="(?:preheader|km-banner|ftr|meta)"[^>]*>.*?</div>',
                  " ", body, flags=re.S)
    real_thai = len(THAI_CHAR_RE.findall(re.sub(r"<[^>]+>", " ", body)))
    assert 4000 < real_thai < MAX_THAI_CHARS


def test_review_skips_llm_when_content_passes():
    gemini = MagicMock()
    editor = EditorAgent(gemini)
    out = editor.review(GOOD)
    assert out == GOOD
    gemini.generate.assert_not_called()


def test_review_calls_llm_when_issues_exist():
    gemini = MagicMock()
    gemini.generate.return_value = "FIXED CONTENT"
    editor = EditorAgent(gemini)
    bad_md = "ไม่มีอะไรเลย"
    out = editor.review(bad_md)
    assert out == "FIXED CONTENT"
    gemini.generate.assert_called_once()
    # Should be tagged for cost tracking
    _, kwargs = gemini.generate.call_args
    assert kwargs["agent_tag"] == "editor"


def test_review_falls_back_to_original_on_llm_error():
    gemini = MagicMock()
    gemini.generate.return_value = "[Error: rate limit]"
    editor = EditorAgent(gemini)
    bad_md = "ไม่มีอะไรเลย"
    out = editor.review(bad_md)
    assert out == bad_md


def test_check_flags_specific_company_name():
    md = GOOD + "\nบริษัท ABC จำกัด ลด 25%"
    issues = EditorAgent.check(md)
    assert any("ชื่อบริษัท" in i for i in issues)


def test_check_passes_generic_company_phrasing():
    """Good content uses 'โรงงานขนาดX แห่งหนึ่ง' which should NOT flag."""
    md = GOOD.replace("โรงแรม 200 ห้องในกรุงเทพ", "โรงงานขนาดกลางแห่งหนึ่งในไทย")
    issues = EditorAgent.check(md)
    assert not any("ชื่อบริษัท" in i for i in issues)


# Fixtures captured verbatim from a gemini-3.8-flash translator run
# (2026-09-11, Scope 1 MRV). Email clients render these as raw LaTeX.
_REAL_UNIT = r"มีการปล่อย Scope 1 สูงถึง 26,800 $\text{tCO}_2\text{e}$/ปี"
_REAL_FORMULA = (
    r"- $\text{GHG Emissions (tCO}_2\text{e)} = \text{Activity Data} "
    r"\times \text{Net Calorific Value (NCV)} \times \text{Emission Factor (EF)}$"
)


def test_strip_latex_unit_from_real_output():
    assert EditorAgent.strip_latex(_REAL_UNIT) == "มีการปล่อย Scope 1 สูงถึง 26,800 tCO2e/ปี"


def test_strip_latex_formula_from_real_output():
    assert EditorAgent.strip_latex(_REAL_FORMULA) == (
        "- GHG Emissions (tCO2e) = Activity Data × Net Calorific Value (NCV)"
        " × Emission Factor (EF)"
    )


def test_strip_latex_leaves_plain_dollar_amounts_alone():
    md = "งบ $100 และ $250 ต่อจุด"
    assert EditorAgent.strip_latex(md) == md


def test_review_strips_latex_even_when_checks_pass():
    gemini = MagicMock()
    md = GOOD + "\n" + _REAL_UNIT
    out = EditorAgent(gemini).review(md)
    assert "$" not in out and r"\text" not in out
    gemini.generate.assert_not_called()


def test_greenhouse_gas_is_not_a_company_name():
    # Captured from the 2026-09-11 production email: "เรือนกระจก" ends in
    # "จก", which matched the company-abbreviation pattern and forced a
    # needless editor regen (the only false positive in 20 archived posts).
    md = "ปล่อยก๊าซเรือนกระจก Scope 1 ประมาณ 26,500 tCO2e/ปี"
    assert not any("ชื่อบริษัท" in i for i in EditorAgent.check(md))


def test_thai_company_abbreviations_still_flagged():
    for md in ["ลูกค้าคือ บจก. สยามเคมี ลด 20%", "ร่วมกับ หจก. ทองดี ลด 20%"]:
        assert any("ชื่อบริษัท" in i for i in EditorAgent.check(md)), md


CHECKLIST_OK = """## 💡 ประเด็นวันนี้
x

## 🧰 Checklist เดินหน้างาน

- ☐ วัดอุณหภูมิน้ำเย็นออก ควรอยู่ 7 °C ถ้าสูงกว่าแปลว่าโหลดเกิน
- ☐ วัด Excess air ควร 15-20% ถ้าเกินแปลว่าสูญเสียความร้อน
- ☐ อ่านค่าความดันตกคร่อม filter ควร < 250 Pa ถ้าเกินต้องล้าง
- ☐ ตรวจ schedule เครื่องทำงานนอกเวลาหรือไม่
- ☐ ตรวจฉนวนท่อมีจุดชำรุดหรือไม่
- ☐ ตรวจ log การบำรุงรักษาย้อนหลัง 12 เดือน

## 3. Consultant Move
ถาม

## 4. Knowledge Capture
สรุป

## 📖 ศัพท์น่ารู้
- COP = ประสิทธิภาพ
"""


def test_checklist_kit_passes_its_gate():
    assert EditorAgent.check(CHECKLIST_OK, kit="checklist") == []


def test_checklist_with_square_brackets_is_rejected():
    md = CHECKLIST_OK.replace("- ☐ ", "- [ ] ")
    assert any("☐" in i for i in EditorAgent.check(md, kit="checklist"))


def test_square_bracket_text_mid_line_is_not_flagged():
    # No-cry-wolf: only a line that STARTS with '- [ ]' is a fake checkbox.
    md = CHECKLIST_OK + "\nอย่าใช้รูปแบบ - [ ] ในอีเมล\n"
    assert not any("☐" in i for i in EditorAgent.check(md, kit="checklist"))


def test_checklist_needs_at_least_six_items():
    md = CHECKLIST_OK.replace(
        "- ☐ ตรวจ log การบำรุงรักษาย้อนหลัง 12 เดือน\n", "")
    assert any("6" in i for i in EditorAgent.check(md, kit="checklist"))


def test_checklist_needs_three_items_with_numbers():
    md = CHECKLIST_OK.replace("7 °C", "ค่าปกติ").replace("15-20%", "ค่าปกติ")
    assert any("ตัวเลข" in i and "checklist" in i
               for i in EditorAgent.check(md, kit="checklist"))


def test_missing_kit_section_is_flagged():
    md = CHECKLIST_OK.replace("## 🧰 Checklist เดินหน้างาน", "## 4. Takeaways")
    assert any("🧰" in i for i in EditorAgent.check(md, kit="checklist"))


def test_no_kit_means_no_kit_gate():
    md = CHECKLIST_OK.replace("## 🧰 Checklist เดินหน้างาน", "## 4. Takeaways")
    assert not any("🧰" in i for i in EditorAgent.check(md))


QUESTIONS_OK = """## 💡 ประเด็นวันนี้
x

## 🧰 ชุดคำถามเจาะลูกค้า

- ค่าไฟต่อเดือนอยู่ที่เท่าไร?
- แบ่งเป็นระบบอะไรบ้าง?
- ระบบไหนเดินเกินเวลางาน?
- เคยวัดประสิทธิภาพล่าสุดเมื่อไร?

**ลูกค้า:** "แพงไป"
**ตอบ:** "คืนทุน 2 ปี"

**ลูกค้า:** "ไม่มีเวลา"
**ตอบ:** "เสี่ยงเสีย 5% ต่อปี"

## 3. Consultant Move
ถาม

## 4. Knowledge Capture
สรุป

## 📖 ศัพท์น่ารู้
- COP = ประสิทธิภาพ
"""


def test_questions_kit_passes_its_gate():
    issues = EditorAgent.check(QUESTIONS_OK, kit="questions")
    assert not any("คำถาม" in i or "objection" in i for i in issues)


def test_questions_kit_needs_four_questions():
    md = QUESTIONS_OK.replace("- ระบบไหนเดินเกินเวลางาน?\n", "")
    assert any("คำถาม" in i for i in EditorAgent.check(md, kit="questions"))


def test_questions_outside_the_kit_do_not_count():
    md = QUESTIONS_OK.replace("- ระบบไหนเดินเกินเวลางาน?\n", "")
    md = md.replace("ถาม\n\n## 4.", "ทำไม?\nอะไร?\n\n## 4.")
    assert any("คำถาม" in i for i in EditorAgent.check(md, kit="questions"))


def test_questions_kit_needs_two_objections():
    md = QUESTIONS_OK.replace('**ลูกค้า:** "ไม่มีเวลา"', '"ไม่มีเวลา"')
    assert any("objection" in i for i in EditorAgent.check(md, kit="questions"))


CALC_OK = CHECKLIST_OK.replace(
    "## 🧰 Checklist เดินหน้างาน",
    "## 🧰 สูตรคำนวณพร้อมใช้\n\nประหยัด = kWh × 4.2 บาท/kWh — ที่มา: ค่าไฟเฉลี่ย กฟภ.\n"
    "ตัวอย่าง: 1000 kWh × 4.2 บาท/kWh = 4200 บาท/ปี\n",
)


def test_calculator_kit_passes_its_gate():
    issues = EditorAgent.check(CALC_OK, kit="calculator")
    assert not any("สูตร" in i or "ที่มา" in i for i in issues)


def test_calculator_listed_reference_figure_without_its_source_fails():
    """'4.2 บาท/kWh' IS in REFERENCE_FIGURES, so quoting it bare must fail.
    (Before the A7/Task-8 fix this test passed for the wrong reason: the gate
    demanded a source tag from every calculator kit, listed figure or not.)"""
    md = CALC_OK.replace(" — ที่มา: ค่าไฟเฉลี่ย กฟภ.", "")
    assert "4.2 บาท/kWh" in md
    assert any("ที่มา" in i for i in EditorAgent.check(md, kit="calculator"))


def test_calculator_kit_with_no_listed_figure_needs_no_source():
    """Task 8 resolved A7 into three cases: only a figure taken FROM
    REFERENCE_FIGURES carries its source. A kit whose numbers are all
    'ประมาณการ' has no source to quote — asking for one made the repair call
    invent one, in the section consultants read out to customers."""
    md = CALC_OK.replace(
        "ประหยัด = kWh × 4.2 บาท/kWh — ที่มา: ค่าไฟเฉลี่ย กฟภ.\n"
        "ตัวอย่าง: 1000 kWh × 4.2 บาท/kWh = 4200 บาท/ปี\n",
        "ประหยัด (บาท/ปี) = kWh/ปี × ค่าไฟที่โรงงานจ่าย (บาท/kWh)\n"
        "ตัวแปร: การใช้ไฟ 180000 kWh/ปี (ประมาณการ)\n"
        "ตัวอย่าง: 27000 kWh/ปี × 3.8 บาท/kWh = 102600 บาท/ปี (ประมาณการ)\n",
    )
    assert "ที่มา" not in md
    assert not any("ที่มา" in i for i in EditorAgent.check(md, kit="calculator"))


REVIEW_REPRO_KIT = """## 🧰 สูตรคำนวณพร้อมใช้
- ประหยัด (บาท/ปี) = kWh/ปี x 4.2 บาท/kWh
- ตัวแปร: การใช้ไฟ 180000 kWh/ปี (ประมาณการ)
- ตัวอย่าง: 27000 kWh/ปี x 4.2 บาท/kWh = 113400 บาท/ปี
"""


def test_review_repro_kit_still_fails_because_it_quotes_the_listed_tariff():
    """The markdown the final review offered as a false positive quotes
    4.2 บาท/kWh, which IS a REFERENCE_FIGURES value — so the gate is right to
    fire on it. The gate must name the figure, not ask for a source in
    general."""
    issues = EditorAgent._kit_issues(REVIEW_REPRO_KIT, "calculator")
    assert any("4.2บาท/kWh" in i for i in issues)


def test_the_same_kit_passes_once_the_listed_figure_is_sourced():
    md = REVIEW_REPRO_KIT.replace(
        "= kWh/ปี x 4.2 บาท/kWh",
        "= kWh/ปี x 4.2 บาท/kWh — ที่มา: PEA/MEA tariff 2569",
    )
    assert not any("ที่มา" in i
                   for i in EditorAgent._kit_issues(md, "calculator"))


def test_calculator_formula_must_be_inside_the_kit_section():
    # The glossary line 'COP = ...' has '=' too; it must not satisfy the gate.
    md = CALC_OK.replace("ประหยัด = kWh", "ประหยัดคือ kWh").replace(
        "บาท/kWh = 4200", "บาท/kWh เป็น 4200")
    body = md.split("## 🧰")[1].split("## 3.")[0]
    assert "=" not in body and "=" in md
    assert any("'='" in i for i in EditorAgent.check(md, kit="calculator"))


def test_assigned_scene_must_appear():
    issues = EditorAgent.check(CHECKLIST_OK, kit="checklist", scene="โรงแรมริมทะเล")
    assert any("ฉาก" in i for i in issues)


def test_assigned_scene_present_passes():
    md = CHECKLIST_OK.replace("\nx\n", "\nที่โรงแรมริมทะเลแห่งหนึ่ง\n")
    issues = EditorAgent.check(md, kit="checklist", scene="โรงแรมริมทะเล")
    assert not any("ฉาก" in i for i in issues)


def test_recall_block_requires_its_answer_box():
    md = CHECKLIST_OK + "\n## 🔁 ทวนของเก่า\n- คำถาม?\n"
    assert any("เฉลย" in i for i in EditorAgent.check(md, kit="checklist"))


def test_recall_block_with_answer_box_passes():
    md = CHECKLIST_OK + "\n## 🔁 ทวนของเก่า\n- คำถาม?\n\n## 🔑 เฉลย\n- ตอบ\n"
    assert not any("เฉลย" in i for i in EditorAgent.check(md, kit="checklist"))


def test_review_passes_kit_and_scene_to_check():
    gemini = MagicMock()
    gemini.generate.return_value = "FIXED"
    out = EditorAgent(gemini).review(CHECKLIST_OK, kit="checklist",
                                     scene="โรงแรมริมทะเล")
    assert out == "FIXED"
    assert "ฉาก" in gemini.generate.call_args.args[0]


def test_repair_prompt_forbids_dropping_kit_and_recall_sections():
    gemini = MagicMock()
    gemini.generate.return_value = "FIXED"
    EditorAgent(gemini).review("ไม่มีอะไรเลย")
    assert "🧰 / 🔁 / 🔑" in gemini.generate.call_args.args[0]


def test_anchor_phrase_in_body_prose_does_not_satisfy_the_gate():
    md = GOOD.replace("## 3. Consultant Move", "## 3. อื่น").replace(
        "## 4. Knowledge Capture", "## 4. อื่น")
    md += "\nวันนี้พูดถึง Consultant Move และ Knowledge Capture ในประโยค\n"
    issues = EditorAgent.check(md)
    assert any("Consultant Move" in i for i in issues)
    assert any("Knowledge Capture" in i for i in issues)


def test_anchor_heading_with_suffix_is_rejected():
    md = GOOD.replace("## 3. Consultant Move", "## 3. Consultant Move: ถามให้เป็น")
    assert any("Consultant Move" in i for i in EditorAgent.check(md))


def test_inline_glossary_form_is_rejected():
    md = GOOD.replace("## 📖 ศัพท์น่ารู้\n", "📖 ศัพท์น่ารู้: ")
    assert any("ศัพท์น่ารู้" in i for i in EditorAgent.check(md))


def test_scene_match_ignores_whitespace_differences():
    md = CHECKLIST_OK.replace("\nx\n", "\nโรงพยาบาล  24  ชั่วโมง เปิดตลอด\n")
    assert not any("ฉาก" in i for i in
                   EditorAgent.check(md, kit="checklist", scene="โรงพยาบาล 24 ชั่วโมง"))
    md2 = CHECKLIST_OK.replace("\nx\n", "\nCFO ของกลุ่มค้าปลีก\n")
    assert any("ฉาก" in i for i in
               EditorAgent.check(md2, kit="checklist", scene="CFO กลุ่มค้าปลีก"))


@pytest.mark.parametrize("unit", ["บาท", "%", "ปี", "ชม", "ชั่วโมง", "kWh", "kW", "MW",
                                  "°C", "Pa", "kPa", "bar", "kg", "ตัน", "rpm", "ppm",
                                  "V", "A", "Hz", "m3/h", "L/s", "RT", "hours", "years"])
def test_unit_list_matches_a_number_with_each_unit(unit):
    assert NUMBER_WITH_UNIT_RE.search(f"ค่า 12 {unit} ปกติ"), unit


@pytest.mark.parametrize("text", ["2 parameters", "3 parts", "2 barriers", "5 months",
                                  "12 เดือน", "30 วัน", "3 Apples", "2 a day"])
def test_non_readings_do_not_count_as_units(text):
    assert not NUMBER_WITH_UNIT_RE.search(text), text


def test_missing_kit_heading_names_the_expected_label():
    md = CHECKLIST_OK.replace("## 🧰 Checklist เดินหน้างาน", "## 4. Takeaways")
    assert any("Checklist เดินหน้างาน" in i for i in EditorAgent.check(md, kit="checklist"))


def test_unknown_kit_is_an_issue_not_a_crash():
    issues = EditorAgent.check(CHECKLIST_OK, kit="nonsense")
    assert any("nonsense" in i for i in issues)


def test_recall_flag_requires_the_whole_block():
    assert any("🔁" in i for i in EditorAgent.check(CHECKLIST_OK, kit="checklist", recall=True))
    only_recall = CHECKLIST_OK + "\n## 🔁 ทวนของเก่า\n- ข้อ?\n"
    assert any("เฉลย" in i for i in EditorAgent.check(only_recall, kit="checklist", recall=True))
    full = only_recall + "\n## 🔑 เฉลย\n- ตอบ\n"
    assert EditorAgent.check(full, kit="checklist", recall=True) == []
    assert EditorAgent.check(CHECKLIST_OK, kit="checklist") == []


def test_review_logs_when_repair_still_fails(caplog):
    gemini = MagicMock()
    gemini.generate.return_value = "ยังพังอยู่"
    with caplog.at_level("WARNING"):
        out = EditorAgent(gemini).review("ไม่มีอะไรเลย")
    assert out == "ยังพังอยู่"
    assert "repair still failing" in caplog.text
    gemini.generate.assert_called_once()


def test_review_is_quiet_when_repair_succeeds(caplog):
    gemini = MagicMock()
    gemini.generate.return_value = GOOD
    with caplog.at_level("WARNING"):
        EditorAgent(gemini).review("ไม่มีอะไรเลย")
    assert "repair still failing" not in caplog.text


def test_review_passes_recall_to_check():
    gemini = MagicMock()
    gemini.generate.return_value = "FIXED"
    EditorAgent(gemini).review(CHECKLIST_OK, kit="checklist", recall=True)
    assert "🔁" in gemini.generate.call_args.args[0]


def test_last_repair_count_is_zero_when_content_passes():
    editor = EditorAgent(MagicMock())
    assert editor.last_repair_count == 0
    editor.review(GOOD)
    assert editor.last_repair_count == 0


def test_last_repair_count_is_one_after_a_repair_and_resets():
    gemini = MagicMock()
    gemini.generate.return_value = "FIXED CONTENT"
    editor = EditorAgent(gemini)
    editor.review("ไม่มีอะไรเลย")
    assert editor.last_repair_count == 1
    editor.review(GOOD)
    assert editor.last_repair_count == 0
