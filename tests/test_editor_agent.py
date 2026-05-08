from unittest.mock import MagicMock

from src.agents.editor_agent import EditorAgent

GOOD = """สวัสดีทีมงาน Sales และ Technical ทุกท่าน

## 1. Chiller ในมุมมอง Consultant

ลูกค้าไม่ต้องการ chiller ใหม่ แต่ต้องการลดค่าไฟที่วัดผลได้

## 2. Case Study

**Situation:** โรงแรม 200 ห้องในกรุงเทพ ค่าไฟเดือนละ 250000 บาท

**Complication:** chiller ทำงาน 800 kW แต่ไม่มี data baseline

**Consultant's Approach:**
- วิเคราะห์ COP จริงด้วย data logger 5000 บาท
- เทียบกับ ASHRAE standard

**Result:** ลด COP loss ได้ 25% คืนทุนภายใน 3 ปี

## 3. Takeaways

**ทีม Sales:**
- Pitch ด้วย ROI ไม่ใช่ spec

**ทีม Technical:**
- วัด COP ก่อนเสนอ solution

📖 ศัพท์น่ารู้: COP = ค่าประสิทธิภาพ | Fouling = คราบสะสม
"""


def test_check_passes_full_article():
    assert EditorAgent.check(GOOD) == []


def test_check_flags_missing_consultant_move():
    md = GOOD.replace("Case Study", "กรณีศึกษา").replace("Situation", "สถานการณ์").replace("Complication", "ปัญหา")
    issues = EditorAgent.check(md)
    assert any("Case Study" in i for i in issues)


def test_check_flags_missing_glossary():
    md = GOOD.replace("📖 ศัพท์น่ารู้: COP = ค่าประสิทธิภาพ | Fouling = คราบสะสม", "")
    issues = EditorAgent.check(md)
    assert any("glossary" in i for i in issues)


def test_check_flags_too_few_numbers():
    md = "## หัว\nเนื้อหาไม่มีตัวเลข\n\n## Consultant Move\nถามลูกค้า\n\n📖 ศัพท์น่ารู้: A=B"
    issues = EditorAgent.check(md)
    assert any("ตัวเลขจริง" in i for i in issues)


def test_check_recognizes_thai_units():
    md = "ค่าไฟ 250000 บาท ใช้ไฟ 800 kWh ลด 25% ROI 2 ปี"
    md += "\n\n## Consultant Move\nถาม\n\n📖 ศัพท์น่ารู้: A=B"
    issues = EditorAgent.check(md)
    assert not any("ตัวเลข" in i for i in issues)


def test_check_flags_overlong_content():
    long_md = "word " * 800 + "\n## Consultant Move\nถาม\n\n📖 ศัพท์น่ารู้: A=B\n5000 บาท 800 kWh 25%"
    issues = EditorAgent.check(long_md)
    assert any("ยาว" in i for i in issues)


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
