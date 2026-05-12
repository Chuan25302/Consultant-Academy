"""
Local preview — renders the KM site against a small set of fixture posts
without touching Drive. Use this to iterate on templates/CSS quickly.

  python tools/preview_site.py            # writes to ./docs_preview/
  python tools/preview_site.py --open     # also opens index.html in browser
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.build_site import Post, render_site

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs_preview"


SAMPLE_BODY_TECH = (
    '<div class="wrap"><div class="bd">'
    '<h2>💡 ประเด็นวันนี้</h2>'
    '<p>ปั๊มหอยโข่ง (Centrifugal Pump) ทำงานด้วยการแปลงพลังงานจลน์จากการหมุน '
    'ของใบพัดเป็นพลังงานความดันของของไหล หลักการนี้ใช้ในโรงกลั่นทั่วโลก</p>'
    '<h2>เนื้อหาเชิงเทคนิค</h2>'
    '<p>การเลือก operating point ที่เหมาะสมบน <strong>pump curve</strong> '
    'คือหัวใจของการใช้ปั๊มอย่างมีประสิทธิภาพ. ทำผิดจะส่งผลให้</p>'
    '<ul><li>ค่าไฟสูงขึ้น 15–30%</li>'
    '<li>อายุการใช้งานของ seal และ bearing ลดลง</li>'
    '<li>เกิด cavitation ที่สึกกร่อนใบพัดอย่างถาวร</li></ul>'
    '<h2>Consultant Move</h2>'
    '<p>เมื่อเจอลูกค้าพูดว่า "ปั๊มเสียบ่อย" ให้ถามต่อทันที — เสียจาก seal? bearing? '
    'หรือ impeller? เพราะ 3 อาการนี้บ่งบอกปัญหาคนละชนิดและคนละทางแก้</p>'
    '</div></div>'
)
SAMPLE_BODY_FRAMEWORK = (
    '<div class="wrap"><div class="bd">'
    '<h2>💡 ประเด็นวันนี้</h2>'
    '<p>MECE = Mutually Exclusive, Collectively Exhaustive — '
    'หลักการแบ่งปัญหาเพื่อให้มั่นใจว่าไม่มีอะไรซ้ำ และไม่มีอะไรขาดหาย</p>'
    '<h2>ใช้อย่างไรเวลา diagnose โรงงาน</h2>'
    '<p>เมื่อเจอปัญหาการใช้พลังงานสูงผิดปกติ ให้แบ่งเป็น 3 ฝั่งให้ครบ:</p>'
    '<ul><li><strong>Supply side</strong> — แหล่งพลังงานเข้าโรงงาน</li>'
    '<li><strong>Conversion</strong> — boiler, chiller, compressor</li>'
    '<li><strong>End-use</strong> — process unit ที่ใช้พลังงานจริง</li></ul>'
    '<blockquote>การคิดแบบ MECE บังคับให้เราไม่ "เลือกข้างที่ถนัด" '
    'แต่บังคับให้เราตรวจครบทุกฝั่ง</blockquote>'
    '</div></div>'
)
SAMPLE_BODY_SUS = (
    '<div class="wrap"><div class="bd">'
    '<h2>💡 ประเด็นวันนี้</h2>'
    '<p>Scope 1, 2, 3 ของ GHG Protocol คือกรอบมาตรฐานที่ทุกองค์กรใช้รายงาน carbon footprint</p>'
    '<h2>ความแตกต่างที่สำคัญ</h2>'
    '<ul><li><strong>Scope 1</strong> — direct emissions (เผาเชื้อเพลิงในโรงงานเอง)</li>'
    '<li><strong>Scope 2</strong> — ไฟฟ้าที่ซื้อมาใช้</li>'
    '<li><strong>Scope 3</strong> — ห่วงโซ่อุปทาน (ใหญ่ที่สุดและยากที่สุด)</li></ul>'
    '</div></div>'
)


def fixtures() -> list[Post]:
    """A handful of realistic posts covering 3 pillars, 2 clusters, 3 levels.
    Enough to exercise every layout in the site."""
    return [
        Post(date="2026-05-14", title="กรอบ MECE สำหรับ Diagnose โรงงาน",
             pillar="FRAMEWORK", cluster="Diagnostic Frameworks", level=1,
             industry="General", keywords=["mece"], body_html=SAMPLE_BODY_FRAMEWORK,
             tldr="MECE คือหลักแบ่งปัญหาเพื่อให้ครอบคลุมและไม่ซ้ำ — ใช้เป็นจุดตั้งต้นทุกครั้งที่ diagnose โรงงาน"),
        Post(date="2026-05-13", title="วิเคราะห์ Pump Curve เลือก Operating Point",
             pillar="TECHNICAL", cluster="Pumps & Compressors", level=2,
             industry="Refining", keywords=["pump"], body_html=SAMPLE_BODY_TECH,
             tldr="อ่าน pump curve เป็น เลือก operating point ตรงกับโหลดจริง ลดค่าไฟ 15–30%"),
        Post(date="2026-05-12", title="ทำความรู้จักปั๊มหอยโข่งฉบับเริ่มต้น",
             pillar="TECHNICAL", cluster="Pumps & Compressors", level=1,
             industry="Refining", keywords=["pump"], body_html=SAMPLE_BODY_TECH,
             tldr="หลักการทำงานของปั๊มหอยโข่งและจุดที่มักทำให้เสียบ่อยที่สุด"),
        Post(date="2026-05-09", title="Scope 1/2/3 ฉบับเข้าใจง่าย",
             pillar="SUSTAINABILITY", cluster="Carbon Accounting", level=1,
             industry="General", keywords=["ghg"], body_html=SAMPLE_BODY_SUS,
             tldr="คู่มือเริ่มต้น GHG Protocol — Scope 1/2/3 ต่างกันยังไง"),
        Post(date="2026-05-08", title="วัด Scope 3 จาก supplier — เริ่มที่ไหน",
             pillar="SUSTAINABILITY", cluster="Carbon Accounting", level=2,
             industry="General", keywords=["scope3"], body_html=SAMPLE_BODY_SUS,
             tldr="วิธีเริ่มเก็บข้อมูล Scope 3 จาก supplier โดยไม่ติดที่ความสมบูรณ์ของข้อมูล"),
        Post(date="2026-05-07", title="Stakeholder Mapping ก่อนเข้าพบลูกค้า",
             pillar="SOFTSKILL", cluster="Client Engagement", level=1,
             industry="General", keywords=["stakeholder"], body_html=SAMPLE_BODY_FRAMEWORK,
             tldr="แผนผังผู้มีส่วนได้เสียที่ที่ปรึกษามือใหม่มักลืมจัดทำ"),
        Post(date="2026-05-06", title="ISO 50001 vs ISO 14001 ต่างกันอย่างไร",
             pillar="COMPLIANCE", cluster="Energy Standards", level=1,
             industry="General", keywords=["iso"], body_html=SAMPLE_BODY_SUS,
             tldr="เทียบมาตรฐาน 2 ตัวที่ลูกค้ามักสับสน — เลือกใช้อันไหนเมื่อไหร่"),
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=str(DEFAULT_OUT))
    p.add_argument("--open", action="store_true", help="Open the rendered index in browser")
    args = p.parse_args()
    out = Path(args.output).resolve()
    render_site(fixtures(), out)
    sys.stdout.write(f"[OK] Preview written to: {out}\n")
    sys.stdout.write(f"     Open: file:///{out.as_posix()}/index.html\n")
    sys.stdout.flush()
    if args.open:
        webbrowser.open((out / "index.html").as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
