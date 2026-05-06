import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.agents.designer_agent import PILLAR_CONFIG, DesignerAgent

TZ = ZoneInfo("Asia/Bangkok")


def _meta(pillar="TECHNICAL", industry="Hospitality"):
    return {
        "pillar": pillar,
        "topic": "Test Topic",
        "industry": industry,
        "date": datetime(2024, 5, 6, tzinfo=TZ),
    }


@pytest.mark.parametrize("pillar", list(PILLAR_CONFIG.keys()))
def test_renders_all_pillars(pillar):
    html = DesignerAgent.create_email("## หัวข้อ\ntext", _meta(pillar=pillar))
    assert "<!DOCTYPE html>" in html
    assert "Test Topic" in html
    assert PILLAR_CONFIG[pillar]["color"] in html
    assert PILLAR_CONFIG[pillar]["label"] in html


def test_compliance_pillar_registered():
    assert "COMPLIANCE" in PILLAR_CONFIG
    assert PILLAR_CONFIG["COMPLIANCE"]["label"] == "มาตรฐาน/Compliance"


def test_industry_badge_shown():
    html = DesignerAgent.create_email("test", _meta(industry="Steel"))
    assert "🏭 Steel" in html


def test_industry_badge_hidden_for_general():
    html = DesignerAgent.create_email("test", _meta(industry="General"))
    assert "🏭 General" not in html


def test_industry_badge_hidden_for_thai_general():
    html = DesignerAgent.create_email("test", _meta(industry="ทั่วไป"))
    assert "🏭 ทั่วไป" not in html


def test_buddhist_year_displayed():
    html = DesignerAgent.create_email("test", _meta())
    # 2024 + 543 = 2567
    assert "2567" in html
    assert "พฤษภาคม" in html


def test_consultant_move_wrapped():
    html = DesignerAgent.create_email(
        "## สถานการณ์\nfoo\n\n## Consultant Move\nถามลูกค้า\n",
        _meta(),
    )
    assert 'class="cmove"' in html or "cmove" in html
    assert "💬 Consultant Move" in html


def test_glossary_wrapped():
    html = DesignerAgent.create_email(
        "เนื้อหา\n\n📖 ศัพท์น่ารู้: COP = ค่าประสิทธิภาพ | VFD = ตัวขับ",
        _meta(),
    )
    assert "glossary" in html
    assert "COP = ค่าประสิทธิภาพ" in html


def test_markdown_bold_rendered():
    html = DesignerAgent.create_email("**สำคัญ** มาก", _meta())
    # premailer inlines style="..." onto <strong>, so check via regex
    assert re.search(r"<strong[^>]*>สำคัญ</strong>", html)


def test_markdown_bullets_rendered():
    html = DesignerAgent.create_email("- ข้อ 1\n- ข้อ 2\n- ข้อ 3", _meta())
    assert re.search(r"<ul[^>]*>", html)
    assert re.search(r"<li[^>]*>ข้อ 1</li>", html)
    assert re.search(r"<li[^>]*>ข้อ 3</li>", html)


def test_markdown_h2_h3_rendered():
    html = DesignerAgent.create_email("## หัวใหญ่\n### หัวเล็ก", _meta())
    assert re.search(r"<h2[^>]*>หัวใหญ่</h2>", html)
    assert re.search(r"<h3[^>]*>หัวเล็ก</h3>", html)


def test_inline_styles_present():
    """premailer should inline at least some CSS so Gmail/Outlook renders it."""
    html = DesignerAgent.create_email("test", _meta())
    # Body and header should have inline style attributes after premailer runs
    assert html.count("style=") > 5


def test_unknown_pillar_falls_back_to_technical():
    html = DesignerAgent.create_email("test", {"pillar": "BOGUS", "topic": "T",
                                                "date": datetime(2024, 5, 6, tzinfo=TZ)})
    assert PILLAR_CONFIG["TECHNICAL"]["color"] in html


def test_md_to_html_idempotent_on_empty():
    html = DesignerAgent._md_to_html("")
    assert html == ""
