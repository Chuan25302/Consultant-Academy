"""
Static site builder for the Consultant Academy KM archive.

Walks the Drive Email Archives folder, cross-references the calendar for
pillar/cluster/level metadata, and emits a small static site to docs/.

Source of truth stays in Drive — this tool only mirrors content to a
browsable form. Re-running it from scratch reproduces the whole site,
so docs/ is safe to delete and rebuild.

CLI:
  python tools/build_site.py
  python tools/build_site.py --output ./docs
  python tools/build_site.py --limit 5     # only build N most recent (smoke test)
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.agents.designer_agent import post_url_path
from src.config.settings import Settings, now_bangkok
from src.integrations.drive_api import DriveAPI
from src.utils.calendar_parser import CalendarParser
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "site" / "templates"
ASSETS_DIR = Path(__file__).resolve().parent / "site" / "assets"
DEFAULT_OUTPUT = ROOT / "_site"

ARCHIVE_FILENAME_RE = re.compile(
    r"^\[Email\]\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\.html$"
)

# Pillar visual config — mirrors designer_agent.PILLAR_CONFIG so the
# site looks consistent with the email. Kept as a separate dict so the
# site can render even if designer's constants drift.
PILLAR_META = {
    "TECHNICAL":      {"slug": "technical",      "icon": "⚙️", "label": "เชิงเทคนิค"},
    "INDUSTRY":       {"slug": "industry",       "icon": "🏭", "label": "อุตสาหกรรม"},
    "FRAMEWORK":      {"slug": "framework",      "icon": "📐", "label": "กรอบการวิเคราะห์"},
    "SOFTSKILL":      {"slug": "softskill",      "icon": "💡", "label": "ทักษะที่ปรึกษา"},
    "COMPLIANCE":     {"slug": "compliance",     "icon": "📜", "label": "Compliance"},
    "SUSTAINABILITY": {"slug": "sustainability", "icon": "🌱", "label": "Sustainability"},
    "RECAP":          {"slug": "recap",          "icon": "📋", "label": "สรุปสัปดาห์"},
    "UNKNOWN":        {"slug": "unknown",        "icon": "📄", "label": "ทั่วไป"},
}

MONTHS_TH = {
    1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
    5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
    9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม",
}

BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.DOTALL | re.IGNORECASE)
TLDR_FROM_BODY_RE = re.compile(
    r'<div class="bd"[^>]*>.*?<p[^>]*>(.*?)</p>',
    re.DOTALL,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Post:
    date: str             # YYYY-MM-DD
    title: str
    pillar: str
    cluster: str
    level: int
    industry: str
    keywords: list[str]
    body_html: str
    tldr: str
    html_file_id: str = ""

    @property
    def dt(self) -> datetime:
        return datetime.strptime(self.date, "%Y-%m-%d")

    @property
    def year(self) -> int: return self.dt.year
    @property
    def month(self) -> int: return self.dt.month
    @property
    def day(self) -> int: return self.dt.day
    @property
    def year_be(self) -> int: return self.dt.year + 543
    @property
    def month_th(self) -> str: return MONTHS_TH[self.dt.month]
    @property
    def date_th(self) -> str: return f"{self.day} {self.month_th} {self.year_be}"
    @property
    def url(self) -> str: return post_url_path(self.dt)

    @property
    def pillar_slug(self) -> str: return PILLAR_META.get(self.pillar, PILLAR_META["UNKNOWN"])["slug"]
    @property
    def pillar_icon(self) -> str: return PILLAR_META.get(self.pillar, PILLAR_META["UNKNOWN"])["icon"]
    @property
    def pillar_label(self) -> str: return PILLAR_META.get(self.pillar, PILLAR_META["UNKNOWN"])["label"]

    @property
    def cluster_slug(self) -> str: return slugify(self.cluster)


def slugify(text: str) -> str:
    """URL-safe ASCII slug. Thai/non-ASCII chars get normalized away;
    if nothing ASCII remains we fall back to a short stable digest so
    every cluster still produces a unique routable path."""
    if not text:
        return "general"
    norm = unicodedata.normalize("NFKD", text)
    ascii_part = norm.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_part).strip("-").lower()
    if not slug:
        # All-Thai cluster: stable hash so identical names route identically.
        import hashlib
        slug = "c-" + hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return slug[:60]


def parse_calendar_metadata(raw: str) -> dict[str, dict]:
    """Read the whole calendar at once, return {date_str: topic_info}.
    Cheaper than calling CalendarParser.get_topic() per post."""
    out: dict[str, dict] = {}
    if not raw:
        return out
    parser = CalendarParser(raw)
    for line in raw.splitlines():
        m = re.search(r"(\d{4}-\d{2}-\d{2})", line)
        if not m:
            continue
        date_str = m.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        topic = parser.get_topic(dt)
        if topic:
            out[date_str] = topic
    return out


def extract_body(archive_html: str) -> str:
    """Pull just the <body>...</body> content out of the email archive.
    Premailer already inlined styles, so this fragment renders fine when
    embedded in the post page; the outer <html>/<head>/<body> chrome is
    discarded (the site shell replaces it). Preheader stays hidden via
    its own CSS in the embedded fragment."""
    m = BODY_RE.search(archive_html or "")
    return m.group(1).strip() if m else (archive_html or "")


def extract_tldr_text(archive_html: str, fallback: str = "") -> str:
    """Plain-text first paragraph of the article body — used as the
    listing card's snippet when __summaries.json doesn't have one."""
    if fallback:
        return fallback
    m = TLDR_FROM_BODY_RE.search(archive_html or "")
    if not m:
        return ""
    text = HTML_TAG_RE.sub("", m.group(1))
    return " ".join(text.split())[:200]


def load_summaries(drive: DriveAPI, settings: Settings) -> dict[str, dict]:
    """Reuse the same __summaries.json that IndexBuilder maintains.
    Maps html_file_id → {tldr, ...}."""
    kb = getattr(settings, "FOLDER_KNOWLEDGE_BASE", "")
    if not kb:
        return {}
    try:
        res = drive._list(  # noqa: SLF001
            f"name='__summaries.json' and '{kb}' in parents and trashed=false",
            fields="files(id)", page_size=1,
        )
        files = res.get("files", []) if isinstance(res, dict) else []
        if not files:
            return {}
        raw = drive.download_file(files[0]["id"])
        if not raw:
            return {}
        import json
        data = json.loads(raw)
        # Re-key by html_file_id so we can look up archive entries directly.
        by_html: dict[str, dict] = {}
        for _docx_id, entry in (data or {}).items():
            html_id = entry.get("html_id")
            if html_id:
                by_html[html_id] = entry
        return by_html
    except Exception as e:
        logger.warning(f"load_summaries failed (non-blocking): {e}")
        return {}


def collect_posts(drive: DriveAPI, settings: Settings, limit: int | None = None) -> list[Post]:
    """Walk Email Archives → for each .html file, look up calendar
    metadata + summary, fetch body, build a Post."""
    archives_folder = getattr(settings, "FOLDER_EMAIL_ARCHIVES", "")
    if not archives_folder:
        logger.error("FOLDER_EMAIL_ARCHIVES is not set — cannot build site")
        return []

    files = drive.walk(archives_folder)
    archive_files = []
    for f in files or []:
        if not isinstance(f, dict):
            continue
        m = ARCHIVE_FILENAME_RE.match(f.get("name", ""))
        if m:
            archive_files.append((m.group(1), m.group(2), f["id"], f.get("name", "")))
    archive_files.sort(key=lambda x: x[0], reverse=True)
    if limit:
        archive_files = archive_files[:limit]

    logger.info(f"Found {len(archive_files)} archived emails")

    raw_calendar = ""
    try:
        cal_id = getattr(settings, "CALENDAR_FILE_ID", "")
        if cal_id:
            raw_calendar = drive.download_file(cal_id) or ""
    except Exception as e:
        logger.warning(f"Calendar download failed (continuing without): {e}")
    calendar_meta = parse_calendar_metadata(raw_calendar)
    logger.info(f"Calendar entries parsed: {len(calendar_meta)}")

    summaries = load_summaries(drive, settings)

    posts: list[Post] = []
    for date_str, title, file_id, _name in archive_files:
        meta = calendar_meta.get(date_str, {})
        html = drive.download_file(file_id) or ""
        if not html:
            logger.warning(f"Empty body, skipping: {date_str} {title}")
            continue
        tldr_from_summary = (summaries.get(file_id) or {}).get("tldr", "")
        post = Post(
            date=date_str,
            title=title,
            pillar=(meta.get("pillar") or "UNKNOWN").upper(),
            cluster=meta.get("cluster") or "General",
            level=int(meta.get("level") or 1),
            industry=meta.get("industry") or "General",
            keywords=list(meta.get("keywords") or []),
            body_html=extract_body(html),
            tldr=extract_tldr_text(html, fallback=tldr_from_summary),
            html_file_id=file_id,
        )
        posts.append(post)
    return posts


# ----- rendering ------------------------------------------------------------

@dataclass
class Group:
    key: str
    label: str
    slug: str
    posts: list[Post] = field(default_factory=list)
    icon: str = ""

    @property
    def count(self) -> int: return len(self.posts)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True, lstrip_blocks=True,
    )


def _rel_for(depth: int) -> str:
    """Relative path back to docs root for a page nested `depth` levels deep.
    All site links are written relative so the same docs/ output works under
    any base path (e.g. github.io/Consultant-Academy)."""
    return "../" * depth if depth > 0 else ""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_site(posts: list[Post], output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    env = _env()
    base_tpl = env.get_template("base.html")
    index_tpl = env.get_template("index.html")
    listing_tpl = env.get_template("listing.html")
    post_tpl = env.get_template("post.html")

    generated_at = now_bangkok().strftime("%Y-%m-%d %H:%M")

    def wrap(body_content: str, *, title: str, description: str, depth: int) -> str:
        return base_tpl.render(
            title=title, description=description,
            body=body_content, rel=_rel_for(depth),
            generated_at=generated_at,
        )

    # ---- group by pillar / cluster / year-month ---------------------------
    by_pillar: dict[str, Group] = {}
    by_cluster: dict[str, Group] = {}
    by_month: dict[tuple[int, int], list[Post]] = {}
    by_year: dict[int, list[Post]] = {}

    for p in posts:
        meta = PILLAR_META.get(p.pillar, PILLAR_META["UNKNOWN"])
        g = by_pillar.setdefault(p.pillar, Group(
            key=p.pillar, label=meta["label"], slug=meta["slug"], icon=meta["icon"]))
        g.posts.append(p)

        cslug = p.cluster_slug
        cg = by_cluster.setdefault(cslug, Group(
            key=p.cluster, label=p.cluster, slug=cslug))
        cg.posts.append(p)

        by_month.setdefault((p.year, p.month), []).append(p)
        by_year.setdefault(p.year, []).append(p)

    # ---- assets -----------------------------------------------------------
    (output_dir / "assets").mkdir(exist_ok=True)
    shutil.copyfile(ASSETS_DIR / "style.css", output_dir / "assets" / "style.css")

    # ---- homepage ---------------------------------------------------------
    latest = sorted(posts, key=lambda p: p.date, reverse=True)[:20]
    pillars_summary = sorted(
        [{"slug": g.slug, "label": g.label, "icon": g.icon, "count": g.count}
         for g in by_pillar.values()],
        key=lambda x: -x["count"],
    )
    top_clusters = sorted(
        [{"slug": g.slug, "name": g.key, "count": g.count}
         for g in by_cluster.values() if g.key != "General"],
        key=lambda x: -x["count"],
    )[:12]
    home_body = index_tpl.render(
        rel="", generated_at=generated_at,
        latest=latest, total_posts=len(posts),
        pillars=pillars_summary, clusters=by_cluster, top_clusters=top_clusters,
    )
    _write(output_dir / "index.html",
           wrap(home_body, title="หน้าแรก", description="คลังความรู้ Consultant Academy",
                depth=0))

    # ---- archive hubs (year, month) --------------------------------------
    years = sorted(by_year.keys(), reverse=True)
    archive_root_links = [
        {"label": f"ปี {y + 543}", "href": f"{y}/", "count": len(by_year[y])}
        for y in years
    ]
    archive_body = listing_tpl.render(
        rel="../", crumbs=[{"label": "หน้าแรก", "href": "../"}, {"label": "ตามวันที่", "href": "./"}],
        heading="คลังตามวันที่", subheading=f"{len(posts)} บทความใน {len(years)} ปี",
        intro=None, child_links=archive_root_links, posts=None,
    )
    _write(output_dir / "archive" / "index.html",
           wrap(archive_body, title="ตามวันที่", description="คลังบทความเรียงตามปี/เดือน", depth=1))

    for y in years:
        months_in_year = sorted({m for (yy, m) in by_month if yy == y}, reverse=True)
        year_links = [
            {"label": MONTHS_TH[m], "href": f"{m:02d}/", "count": len(by_month[(y, m)])}
            for m in months_in_year
        ]
        body = listing_tpl.render(
            rel="../../",
            crumbs=[
                {"label": "หน้าแรก", "href": "../../"},
                {"label": "ตามวันที่", "href": "../"},
                {"label": f"ปี {y + 543}", "href": "./"},
            ],
            heading=f"ปี {y + 543}", subheading=f"{len(by_year[y])} บทความ",
            child_links=year_links, posts=None,
        )
        _write(output_dir / "archive" / f"{y}" / "index.html",
               wrap(body, title=f"ปี {y + 543}", description="คลังบทความรายเดือน", depth=2))

        for m in months_in_year:
            month_posts = sorted(by_month[(y, m)], key=lambda p: p.date, reverse=True)
            body = listing_tpl.render(
                rel="../../../",
                crumbs=[
                    {"label": "หน้าแรก", "href": "../../../"},
                    {"label": "ตามวันที่", "href": "../../"},
                    {"label": f"ปี {y + 543}", "href": "../"},
                    {"label": MONTHS_TH[m], "href": "./"},
                ],
                heading=f"{MONTHS_TH[m]} {y + 543}", subheading=f"{len(month_posts)} บทความ",
                posts=month_posts,
            )
            _write(output_dir / "archive" / f"{y}" / f"{m:02d}" / "index.html",
                   wrap(body, title=f"{MONTHS_TH[m]} {y + 543}", description=f"บทความเดือน {MONTHS_TH[m]}", depth=3))

    # ---- pillar hub + per-pillar pages -----------------------------------
    pillar_links = [
        {"label": f"{g.icon} {g.label}", "href": f"{g.slug}/", "count": g.count}
        for g in sorted(by_pillar.values(), key=lambda g: -g.count)
    ]
    body = listing_tpl.render(
        rel="../",
        crumbs=[{"label": "หน้าแรก", "href": "../"}, {"label": "Pillars", "href": "./"}],
        heading="🧭 6 เสาความรู้",
        subheading="เลือกเสาที่อยากเรียนเชิงลึก แล้วไล่อ่านตามวันที่",
        intro="แต่ละเสาเป็นเลนส์มองธุรกิจพลังงานในมุมที่ต่างกัน — รวมกันคือ toolkit ของ Energy Consultant",
        child_links=pillar_links, posts=None,
    )
    _write(output_dir / "pillars" / "index.html",
           wrap(body, title="6 เสาความรู้", description="คลังบทความตามเสาหลัก", depth=1))

    for pillar_key, g in by_pillar.items():
        sorted_posts = sorted(g.posts, key=lambda p: p.date, reverse=True)
        body = listing_tpl.render(
            rel="../../",
            crumbs=[
                {"label": "หน้าแรก", "href": "../../"},
                {"label": "Pillars", "href": "../"},
                {"label": g.label, "href": "./"},
            ],
            heading=f"{g.icon} {g.label}",
            subheading=f"{g.count} บทความในเสานี้",
            posts=sorted_posts,
        )
        _write(output_dir / "pillars" / g.slug / "index.html",
               wrap(body, title=g.label, description=f"บทความ pillar {g.label}", depth=2))

    # ---- cluster hub + per-cluster pages ---------------------------------
    cluster_links = sorted(
        [{"label": g.key, "href": f"{g.slug}/", "count": g.count}
         for g in by_cluster.values() if g.key != "General"],
        key=lambda x: -x["count"],
    )
    body = listing_tpl.render(
        rel="../",
        crumbs=[{"label": "หน้าแรก", "href": "../"}, {"label": "เรื่อง", "href": "./"}],
        heading="🎯 เลือกเรื่องที่อยากรู้",
        subheading=f"{len(cluster_links)} เรื่อง — แต่ละเรื่องคือ learning path เป็นชุด",
        intro="คลิกเรื่องที่สนใจ จะเห็นบทความเรียงจาก L1 พื้นฐาน → L3 ลึก พร้อมไล่อ่านเป็นซีรีส์",
        child_links=cluster_links, posts=None,
    )
    _write(output_dir / "clusters" / "index.html",
           wrap(body, title="ตามเรื่อง", description="คลังบทความตามเรื่อง", depth=1))

    for cslug, g in by_cluster.items():
        # Within a cluster: surface learning path L1 → L2 → L3 (newest first within each level)
        sorted_posts = sorted(
            g.posts,
            key=lambda p: (p.level, -datetime.strptime(p.date, "%Y-%m-%d").toordinal()),
        )
        # Count posts per level for the learning-path banner
        levels = {1: 0, 2: 0, 3: 0}
        for p in g.posts:
            if p.level in levels:
                levels[p.level] += 1
        learn_path_data = {
            "intro": (
                f"คุณกำลังดูชุดความรู้เรื่อง <strong>{g.key}</strong> — "
                "บทความเรียงจากพื้นฐานไปลึก เริ่มจาก L1 จะปูพื้นที่จำเป็น "
                "L2 ต่อยอด และ L3 ลงรายละเอียดระดับใช้งานจริงกับลูกค้า"
            ),
            "steps": [{"level": lvl, "count": cnt}
                      for lvl, cnt in levels.items() if cnt > 0],
        }
        body = listing_tpl.render(
            rel="../../",
            crumbs=[
                {"label": "หน้าแรก", "href": "../../"},
                {"label": "ตามเรื่อง", "href": "../"},
                {"label": g.key, "href": "./"},
            ],
            heading=f"🎯 {g.key}",
            subheading=f"{g.count} บทความในชุดนี้",
            learn_path=learn_path_data,
            posts=sorted_posts,
        )
        _write(output_dir / "clusters" / g.slug / "index.html",
               wrap(body, title=g.key, description=f"คลังบทความเรื่อง {g.key}", depth=2))

    # ---- post pages -------------------------------------------------------
    for p in posts:
        related = [r for r in by_cluster.get(p.cluster_slug, Group("", "", "")).posts
                   if r.date != p.date]
        related = sorted(related, key=lambda r: r.date, reverse=True)[:5]
        body_html = post_tpl.render(rel="../../../../", post=p, related=related)
        out = output_dir / "posts" / f"{p.year:04d}" / f"{p.month:02d}" / f"{p.day:02d}" / "index.html"
        _write(out, wrap(body_html, title=p.title, description=p.tldr or p.title, depth=4))

    # CNAME / nojekyll — disable Jekyll so leading-underscore dirs (none yet,
    # but defensive) and folders served as-is.
    _write(output_dir / ".nojekyll", "")

    logger.info(f"✅ Built {len(posts)} posts → {output_dir}")


# ---------------------------------------------------------------------------

def main(output_dir: Path, limit: int | None) -> int:
    settings = Settings()
    drive = DriveAPI(settings)
    posts = collect_posts(drive, settings, limit=limit)
    if not posts:
        logger.error("No posts collected — aborting build")
        return 1
    render_site(posts, output_dir)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build Consultant Academy KM site")
    p.add_argument("--output", default=str(DEFAULT_OUTPUT),
                   help="Output directory (default: ./docs)")
    p.add_argument("--limit", type=int, default=None,
                   help="Only build N most recent posts (smoke test)")
    args = p.parse_args()
    sys.exit(main(Path(args.output).resolve(), args.limit))
