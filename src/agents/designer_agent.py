"""
Designer Agent — local HTML rendering, ZERO API cost.
Converts Markdown → professional Thai HTML email with INLINE styles
(via premailer) so it survives Gmail/Outlook stripping.
"""
import logging
import re
from datetime import datetime

import cssutils
from premailer import transform

from src.config.settings import now_bangkok

logger = logging.getLogger(__name__)

# cssutils (used by premailer) doesn't understand CSS3 gradients and logs
# noisy ERRORs. We don't care — un-inlinable rules stay in <style> anyway.
cssutils.log.setLevel(logging.FATAL)

PILLAR_CONFIG = {
    "TECHNICAL": {"color": "#0D47A1", "rgba": "13,71,161",  "icon": "⚙️", "label": "เชิงเทคนิค"},
    "INDUSTRY":  {"color": "#E65100", "rgba": "230,81,0",   "icon": "🏭", "label": "อุตสาหกรรม"},
    "FRAMEWORK": {"color": "#1B5E20", "rgba": "27,94,32",   "icon": "📐", "label": "กรอบการวิเคราะห์"},
    "SOFTSKILL": {"color": "#4A148C", "rgba": "74,20,140",  "icon": "💡", "label": "ทักษะที่ปรึกษา"},
    "RECAP":     {"color": "#37474F", "rgba": "55,71,79",   "icon": "📋", "label": "สรุปประจำสัปดาห์"},
}

MONTHS_TH = {
    1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
    5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
    9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"
}


class DesignerAgent:

    @staticmethod
    def create_email(content: str, metadata: dict) -> str:
        pillar   = metadata.get("pillar", "TECHNICAL")
        topic    = metadata.get("topic", "Untitled")
        date     = metadata.get("date", now_bangkok())
        industry = metadata.get("industry", "")
        cfg      = PILLAR_CONFIG.get(pillar, PILLAR_CONFIG["TECHNICAL"])
        color    = cfg["color"]
        rgba     = cfg["rgba"]

        body     = DesignerAgent._md_to_html(content)
        date_th  = f"{date.day} {MONTHS_TH[date.month]} {date.year + 543}"

        industry_badge = (
            f'<span class="badge">🏭 {industry}</span>'
        ) if industry and industry not in ["General", "ทั่วไป"] else ""

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
.glossary{{background:#F5F5F5;padding:12px 16px;margin-top:20px;border-radius:4px;font-size:12px;color:#666;border-top:2px solid {color}}}
.ftr{{background:#ECEFF1;padding:16px 24px;font-size:11px;color:#78909C;border-top:1px solid #ddd}}
.ftr a{{color:{color};text-decoration:none;margin-right:12px}}
@media(max-width:620px){{.bd,.hdr{{padding:20px 16px}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="tag">{cfg["icon"]} {cfg["label"]}{industry_badge}</div>
    <h2>{topic}</h2>
    <div class="meta">PTT NGR ESP · Consultant Academy · {date_th} · อ่าน 5 นาที</div>
  </div>
  <div class="bd">{body}</div>
  <div class="ftr">
    <strong>📚 Knowledge Base</strong><br>
    <a href="#">Energy Audit Framework</a>
    <a href="#">RCA Decision Tree</a>
    <a href="#">TCO Modeling</a>
    <a href="#">มาตรฐาน TIS/DEDE</a>
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
        h = md
        h = re.sub(r"^## (.+)$",  r"<h2>\1</h2>", h, flags=re.MULTILINE)
        h = re.sub(r"^### (.+)$", r"<h3>\1</h3>", h, flags=re.MULTILINE)
        h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
        h = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", h)
        h = re.sub(r"^\- (.+)$", r"<li>\1</li>", h, flags=re.MULTILINE)
        h = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>\n", h, flags=re.DOTALL)
        h = re.sub(r"(📖 ศัพท์น่ารู้:.+)",
                   r'<div class="glossary">\1</div>', h)
        h = re.sub(
            r"<h2>Consultant Move</h2>(.*?)(?=<h2>|$)",
            r'<div class="cmove"><h3>💬 Consultant Move</h3>\1</div>',
            h, flags=re.DOTALL,
        )
        h = re.sub(
            r"<h3>Consultant Move</h3>(.*?)(?=<h2>|<h3>|<div|$)",
            r'<div class="cmove"><h3>💬 Consultant Move</h3>\1</div>',
            h, flags=re.DOTALL,
        )
        parts = h.split("\n\n")
        out = []
        for p in parts:
            p = p.strip()
            out.append(f"<p>{p}</p>" if p and not p.startswith("<") else p)
        h = "\n".join(out)
        h = h.replace("\n---\n", "<hr style='border:none;border-top:1px solid #ddd;margin:20px 0'>")
        return h
