"""
Designer Agent — local HTML rendering, ZERO API cost.
Converts Markdown → professional Thai HTML email with INLINE styles
(via premailer) so it survives Gmail/Outlook stripping.
Markdown rendering uses the python-markdown library (battle-tested);
glossary + Consultant Move boxes are added by post-processing the HTML.
"""
import logging
import re

import cssutils
import markdown as md_lib
from premailer import transform

from src.config.settings import now_bangkok

logger = logging.getLogger(__name__)

# cssutils (used by premailer) doesn't understand CSS3 gradients and logs
# noisy ERRORs. Un-inlinable rules stay in <style> anyway.
cssutils.log.setLevel(logging.FATAL)

PILLAR_CONFIG = {
    "TECHNICAL":      {"color": "#0D47A1", "rgba": "13,71,161",  "icon": "⚙️", "label": "เชิงเทคนิค"},
    "INDUSTRY":       {"color": "#BF360A", "rgba": "191,54,10",  "icon": "🏭", "label": "อุตสาหกรรม"},
    "FRAMEWORK":      {"color": "#1B5E20", "rgba": "27,94,32",   "icon": "📐", "label": "กรอบการวิเคราะห์"},
    "SOFTSKILL":      {"color": "#4A148C", "rgba": "74,20,140",  "icon": "💡", "label": "ทักษะที่ปรึกษา"},
    "COMPLIANCE":     {"color": "#B71C1C", "rgba": "183,28,28",  "icon": "📜", "label": "มาตรฐาน/Compliance"},
    "SUSTAINABILITY": {"color": "#2E7D32", "rgba": "46,125,50",  "icon": "🌱", "label": "Carbon / Sustainability"},
    "RECAP":          {"color": "#37474F", "rgba": "55,71,79",   "icon": "📋", "label": "สรุปประจำสัปดาห์"},
}

MONTHS_TH = {
    1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
    5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
    9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"
}

# Allow numbered prefix (e.g. "## 3. Consultant Move") that Translator emits.
CMOVE_RE = re.compile(
    r'<h2>(?:\d+\.\s*)?Consultant Move</h2>(.*?)(?=<h2|$)',
    flags=re.DOTALL | re.IGNORECASE,
)
# Inline format (legacy): "📖 ศัพท์น่ารู้: A = ... | B = ..."
GLOSSARY_INLINE_RE = re.compile(
    r'<p>(📖\s*ศัพท์น่ารู้:.+?)</p>',
    flags=re.DOTALL,
)
# List format (current): "## 📖 ศัพท์น่ารู้\n\n- A = ...\n- B = ..."
GLOSSARY_LIST_RE = re.compile(
    r'<h2>📖\s*ศัพท์น่ารู้</h2>\s*<ul>(.*?)</ul>',
    flags=re.DOTALL,
)
# TL;DR section emitted by Translator. Captures the first paragraph after
# the heading so we can mirror it into the inbox preheader.
TLDR_HEADING_RE = re.compile(
    r'^##\s*💡\s*ประเด็นวันนี้\s*$',
    flags=re.MULTILINE,
)
TLDR_BODY_RE = re.compile(
    r'##\s*💡\s*ประเด็นวันนี้\s*\n+(.+?)(?=\n##|\Z)',
    flags=re.DOTALL,
)
# Strip markdown noise to estimate Thai reading time by character count.
MD_NOISE_RE = re.compile(r'[#*_`>\[\]\(\)\|]')


class DesignerAgent:

    @staticmethod
    def create_email(content: str, metadata: dict,
                     related: list[dict] | None = None) -> str:
        pillar   = metadata.get("pillar", "TECHNICAL")
        topic    = metadata.get("topic", "Untitled")
        date     = metadata.get("date") or now_bangkok()
        industry = metadata.get("industry", "")
        level    = metadata.get("level")
        cfg      = PILLAR_CONFIG.get(pillar, PILLAR_CONFIG["TECHNICAL"])
        color    = cfg["color"]
        rgba     = cfg["rgba"]

        body     = DesignerAgent._md_to_html(content)
        date_th  = f"{date.day} {MONTHS_TH[date.month]} {date.year + 543}"

        industry_badge = (
            f'<span class="badge">🏭 {industry}</span>'
        ) if industry and industry not in ["General", "ทั่วไป"] else ""

        level_badge = (
            f'<span class="badge">L{level}</span>'
        ) if level else ""

        footer_links = DesignerAgent._render_footer_links(related, color)
        preheader    = DesignerAgent._extract_tldr(content) or topic
        read_min     = DesignerAgent._reading_minutes(content)

        raw = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
body{{font-family:'Sarabun','Segoe UI',sans-serif;background:#F5F5F5;color:#333;line-height:1.75;margin:0;padding:0}}
.wrap{{max-width:620px;margin:0 auto;background:#fff}}
.hdr{{background:linear-gradient(135deg,{color} 0%,rgba({rgba},0.8) 100%);color:#fff;padding:28px 24px}}
.tag{{display:inline-block;background:rgba(255,255,255,0.2);padding:5px 12px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:12px;color:#fff}}
.badge{{background:rgba(255,255,255,0.15);padding:3px 10px;border-radius:12px;font-size:11px;margin-left:8px;color:#fff}}
.hdr h2{{font-size:22px;font-weight:700;margin:6px 0;line-height:1.4;color:#fff}}
.meta{{font-size:12px;opacity:0.85;margin-top:4px;color:#fff}}
.bd{{padding:28px 24px}}
.bd h2{{color:{color};font-size:18px;border-left:4px solid {color};padding-left:10px;margin:24px 0 10px}}
.bd h3{{color:{color};font-size:15px;margin:18px 0 8px}}
.bd p{{margin:0 0 14px;font-size:14px}}
.bd ul{{margin:8px 0 14px 20px;padding:0}}
.bd li{{margin:6px 0;font-size:14px}}
.bd strong{{color:{color}}}
.cmove{{background:#E8F5E9;border:1px solid #A5D6A7;padding:16px;margin:20px 0;border-radius:6px}}
.cmove h3{{color:#2E7D32;margin:0 0 8px}}
.bd blockquote{{margin:14px 0;padding:10px 16px;border-left:3px solid {color};background:rgba({rgba},0.05);color:#555;font-style:italic;font-size:14px}}
.bd blockquote p{{margin:0}}
.glossary{{background:#F5F5F5;padding:14px 18px;margin-top:24px;border-radius:6px;font-size:13px;color:#555;border-top:3px solid {color}}}
.glossary strong{{color:{color};font-size:13px;display:block;margin-bottom:8px}}
.glossary-list{{margin:0;padding:0 0 0 18px;list-style:disc}}
.glossary-list li{{margin:4px 0;color:#555;font-size:13px}}
.ftr{{background:#ECEFF1;padding:16px 24px;font-size:11px;color:#546E7A;border-top:1px solid #ddd}}
.ftr a{{color:{color};text-decoration:none;margin-right:12px}}
.ftr-mission{{margin-top:12px;padding-top:10px;border-top:1px solid #cfd8dc;color:#546E7A;font-style:italic}}
.preheader{{display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;font-size:1px;line-height:1px;mso-hide:all;overflow:hidden}}
@media(max-width:620px){{.bd,.hdr{{padding:20px 16px}}}}
</style>
</head>
<body>
<div class="preheader">{preheader}</div>
<div class="wrap">
  <div class="hdr">
    <div class="tag">{cfg["icon"]} {cfg["label"]}{industry_badge}{level_badge}</div>
    <h2>{topic}</h2>
    <div class="meta">PTT NGR ESP · Consultant Academy · {date_th} · อ่าน {read_min} นาที</div>
  </div>
  <div class="bd">{body}</div>
  <div class="ftr">
    <strong>📚 อ่านเพิ่มในชุดเดียวกัน</strong><br>
    {footer_links}
    <div class="ftr-mission">PTT NGR ESP · Consultant Academy — ยกระดับทีมจากผู้เชี่ยวชาญ สู่ Energy Consultant ที่ลูกค้าไว้วางใจ</div>
  </div>
</div>
</body>
</html>"""

        try:
            return transform(raw, keep_style_tags=True, remove_classes=False)
        except Exception as e:
            logger.warning(f"premailer inline failed, returning raw HTML: {e}")
            return raw

    @staticmethod
    def _md_to_html(md: str) -> str:
        # `extra` covers def-lists/fenced-code/tables; `nl2br` keeps soft
        # line breaks inside Translator output that mixes prose + bullets.
        html = md_lib.markdown(md, extensions=["sane_lists", "extra", "nl2br"])
        html = CMOVE_RE.sub(
            r'<div class="cmove"><h3>💬 Consultant Move</h3>\1</div>',
            html,
        )
        html = GLOSSARY_LIST_RE.sub(
            r'<div class="glossary"><strong>📖 ศัพท์น่ารู้</strong>'
            r'<ul class="glossary-list">\1</ul></div>',
            html,
        )
        html = GLOSSARY_INLINE_RE.sub(
            r'<div class="glossary">\1</div>',
            html,
        )
        return html

    @staticmethod
    def create_recap_email(content: str, week_num: int,
                           daily_topics: list[dict],
                           date) -> str:
        """Recap-specific layout. Visually distinct from daily emails:
        wider header showing week number + a 5-day timeline strip with
        the actual topics covered Mon–Fri. Body uses the same markdown
        rendering as daily emails."""
        cfg      = PILLAR_CONFIG["RECAP"]
        color    = cfg["color"]
        rgba     = cfg["rgba"]

        body     = DesignerAgent._md_to_html(content)
        date_th  = f"{date.day} {MONTHS_TH[date.month]} {date.year + 543}"

        date_range = ""
        if daily_topics:
            first = daily_topics[0].get("date_th", "")
            last  = daily_topics[-1].get("date_th", "")
            date_range = f"{first} – {last}" if first and last else ""

        timeline = DesignerAgent._render_recap_timeline(daily_topics)
        preheader = f"สรุปสัปดาห์ที่ {week_num} · {len(daily_topics)} หัวข้อจาก Mon–Fri"
        read_min = DesignerAgent._reading_minutes(content)

        raw = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
body{{font-family:'Sarabun','Segoe UI',sans-serif;background:#F5F5F5;color:#333;line-height:1.75;margin:0;padding:0}}
.wrap{{max-width:680px;margin:0 auto;background:#fff}}
.hdr{{background:linear-gradient(135deg,{color} 0%,rgba({rgba},0.85) 100%);color:#fff;padding:32px 28px}}
.hdr .week-tag{{display:inline-block;background:rgba(255,255,255,0.18);padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:10px;letter-spacing:1px;color:#fff}}
.hdr h1{{font-size:28px;font-weight:700;margin:4px 0 6px;color:#fff;line-height:1.3}}
.hdr .range{{font-size:13px;opacity:0.9;color:#fff}}
.timeline{{background:#FAFAFA;border-bottom:1px solid #E0E0E0;padding:14px 18px;display:table;width:100%;box-sizing:border-box}}
.timeline .day{{display:table-cell;text-align:center;padding:6px 4px;font-size:11px;color:#546E7A;border-right:1px dashed #CFD8DC;vertical-align:top}}
.timeline .day:last-child{{border-right:none}}
.timeline .dname{{font-weight:700;color:{color};display:block;margin-bottom:2px}}
.timeline .dtopic{{display:block;font-size:11px;color:#37474F;line-height:1.3;margin-top:2px}}
.bd{{padding:28px 24px}}
.bd h2{{color:{color};font-size:18px;border-left:4px solid {color};padding-left:10px;margin:24px 0 10px}}
.bd h3{{color:{color};font-size:15px;margin:18px 0 8px}}
.bd p{{margin:0 0 14px;font-size:14px}}
.bd ul{{margin:8px 0 14px 20px;padding:0}}
.bd li{{margin:6px 0;font-size:14px}}
.bd strong{{color:{color}}}
.bd blockquote{{margin:14px 0;padding:10px 16px;border-left:3px solid {color};background:rgba({rgba},0.05);color:#555;font-style:italic;font-size:14px}}
.bd blockquote p{{margin:0}}
.ftr{{background:#ECEFF1;padding:16px 24px;font-size:11px;color:#546E7A;border-top:1px solid #ddd}}
.ftr-mission{{margin-top:8px;color:#546E7A;font-style:italic}}
.preheader{{display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;font-size:1px;line-height:1px;mso-hide:all;overflow:hidden}}
@media(max-width:680px){{.bd,.hdr{{padding:20px 16px}}.timeline{{padding:10px 8px}}.timeline .day{{padding:4px 2px;font-size:10px}}}}
</style>
</head>
<body>
<div class="preheader">{preheader}</div>
<div class="wrap">
  <div class="hdr">
    <div class="week-tag">{cfg["icon"]} RECAP · WEEK {week_num}</div>
    <h1>สรุปสัปดาห์ที่ {week_num}</h1>
    <div class="range">{date_range or date_th} · อ่าน {read_min} นาที</div>
  </div>
  <div class="timeline">{timeline}</div>
  <div class="bd">{body}</div>
  <div class="ftr">
    <strong>📚 Knowledge Base</strong> · ดู Master Index บน Drive เพื่ออ่านบทความฉบับเต็มของแต่ละวัน
    <div class="ftr-mission">PTT NGR ESP · Consultant Academy — ยกระดับทีมจากผู้เชี่ยวชาญ สู่ Energy Consultant ที่ลูกค้าไว้วางใจ</div>
  </div>
</div>
</body>
</html>"""

        try:
            return transform(raw, keep_style_tags=True, remove_classes=False)
        except Exception as e:
            logger.warning(f"premailer inline failed, returning raw HTML: {e}")
            return raw

    @staticmethod
    def _render_recap_timeline(daily_topics: list[dict]) -> str:
        """5 horizontal day cells (จ–ศ). Each cell shows day name and
        a short topic label. Falls back to placeholder when a day is
        missing (e.g. holiday). Renders as table cells for email safety."""
        if not daily_topics:
            return '<div class="day" style="display:block;color:#999">(ไม่มีข้อมูล)</div>'
        cells = []
        for d in daily_topics:
            day_th = d.get("day_th", "")
            topic  = d.get("topic", "—")
            short = topic if len(topic) <= 28 else topic[:26] + "…"
            cells.append(
                f'<div class="day">'
                f'<span class="dname">{day_th}</span>'
                f'<span class="dtopic">{short}</span>'
                f'</div>'
            )
        return "".join(cells)

    @staticmethod
    def _extract_tldr(md: str) -> str:
        """Pull plain-text content of the `## 💡 ประเด็นวันนี้` section so
        we can show it in the inbox preheader. Falls back to empty string
        when Translator output didn't include the section."""
        m = TLDR_BODY_RE.search(md or "")
        if not m:
            return ""
        text = m.group(1).strip()
        # Strip markdown emphasis + collapse whitespace; preheaders should
        # be a single short line.
        text = MD_NOISE_RE.sub("", text)
        return " ".join(text.split())[:140]

    @staticmethod
    def _reading_minutes(md: str) -> int:
        """Estimate reading time from non-whitespace Thai/English chars.
        ~500 chars/min is comfortable for technical Thai prose."""
        if not md:
            return 1
        plain = MD_NOISE_RE.sub("", md)
        chars = sum(1 for c in plain if not c.isspace())
        return max(1, round(chars / 500))

    @staticmethod
    def _render_footer_links(related: list[dict] | None, color: str) -> str:
        """Render related-article links into the footer. Falls back to a
        single 'Master Index' pointer when no related items are available
        so the footer is never empty."""
        style = f"color:{color};text-decoration:none;display:block;margin:4px 0"
        if not related:
            return (
                f'<a href="#" style="{style}">'
                'ดู Master Index ของ Knowledge Base</a>'
            )
        items = []
        for a in related:
            file_id = a.get("id")
            title = a.get("title", "")
            level = a.get("level", "")
            date = a.get("date", "")
            url = (
                f"https://drive.google.com/file/d/{file_id}/view"
                if file_id else "#"
            )
            label = f"[L{level}] {title} — {date}" if level else title
            items.append(f'<a href="{url}" style="{style}">{label}</a>')
        return "\n    ".join(items)
