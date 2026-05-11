"""
IndexBuilder — walks the Knowledge Base folder in Drive, then writes a
master index markdown file at the KB root so new hires can browse the
whole library from a single document.

Output format:
    00-Master-Index.md
        # 📚 Consultant Academy — Knowledge Base
        ## 🆕 สำหรับคนใหม่ — แนะนำเรียงนี้
            (Level 1 articles in date order across all 4 pillars)
        ## 📂 ทั้งหมด แยกตาม Pillar
            (grouped: pillar → cluster → article)

Also maintains __summaries.json at the KB root: a small dict mapping
each article's docx file ID to its TL;DR snippet and matching Email
Archive HTML file ID. Used by find_related() so the daily "อ่านเพิ่ม"
section in each email can show:
  - a 1-line summary under each related title (no need to click)
  - a link that opens the browser-renderable HTML (Email Archive)
    instead of the DOCX (which on mobile bounces to the Drive app).
"""
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

MASTER_INDEX_FILENAME = "00-Master-Index.md"
SUMMARIES_FILENAME = "__summaries.json"

PILLAR_LABELS = {
    "01-Technical-Depth":         "TECHNICAL — เนื้อหาเทคนิค",
    "02-Industry-Business-Logic": "INDUSTRY — ตามอุตสาหกรรม",
    "03-Diagnostic-Frameworks":   "FRAMEWORK — กรอบการวิเคราะห์",
    "04-Soft-Skills-Positioning": "SOFTSKILL — ทักษะที่ปรึกษา",
    "05-Standards-Compliance":    "COMPLIANCE — มาตรฐาน/การปฏิบัติตามกฎ",
    "06-Sustainability-Carbon":   "SUSTAINABILITY — Carbon & ESG",
}

# [L1] 2024-05-06 Topic.docx
NEW_FILENAME_RE = re.compile(
    r"^\[L(\d+)\]\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\.[a-z]+$"
)
# 2024-05-06 — TECHNICAL — Topic.docx (legacy)
OLD_FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+[—-]\s+\w+\s+[—-]\s+(.+?)\.[a-z]+$"
)
# [Email] 2024-05-06 Topic.html (in Email Archives folder)
ARCHIVE_FILENAME_RE = re.compile(
    r"^\[Email\]\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\.html$"
)


def _parse_filename(name: str) -> dict | None:
    m = NEW_FILENAME_RE.match(name)
    if m:
        return {"level": int(m.group(1)), "date": m.group(2), "title": m.group(3)}
    m = OLD_FILENAME_RE.match(name)
    if m:
        return {"level": 1, "date": m.group(1), "title": m.group(2)}
    return None


def _drive_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


class IndexBuilder:
    def __init__(self, drive, settings):
        self.drive = drive
        self.settings = settings
        self._articles_cache: list[dict] | None = None
        self._summaries_cache: dict | None = None
        self._archive_index_cache: dict | None = None

    def _summaries_file_id(self) -> str | None:
        """Find existing __summaries.json in KB root, or None if missing."""
        try:
            res = self.drive._list(  # noqa: SLF001
                f"name='{SUMMARIES_FILENAME}' and "
                f"'{self.settings.FOLDER_KNOWLEDGE_BASE}' in parents and "
                f"trashed=false",
                fields="files(id)",
                page_size=1,
            )
            if not isinstance(res, dict):
                return None
            files = res.get("files", [])
            if not isinstance(files, list) or not files:
                return None
            entry = files[0]
            return entry["id"] if isinstance(entry, dict) else None
        except Exception as e:
            logger.warning(f"Could not query summaries file: {e}")
            return None

    def _load_summaries(self) -> dict:
        """Read __summaries.json from KB folder root. Returns empty dict
        when missing or unreadable — find_related stays robust either way."""
        if self._summaries_cache is not None:
            return self._summaries_cache
        file_id = self._summaries_file_id()
        if not file_id:
            self._summaries_cache = {}
            return {}
        try:
            raw = self.drive.download_file(file_id)
        except Exception as e:
            logger.warning(f"download summaries failed: {e}")
            self._summaries_cache = {}
            return {}
        if not isinstance(raw, str) or not raw:
            self._summaries_cache = {}
            return {}
        try:
            data = json.loads(raw)
            self._summaries_cache = data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            logger.warning("__summaries.json malformed — treating as empty")
            self._summaries_cache = {}
        return self._summaries_cache

    def _collect_email_archive_ids(self) -> dict[tuple[str, str], str]:
        """Walk Email Archives → return {(date, title): html_file_id}.
        Lets us link the related section to the browser-renderable HTML
        instead of the DOCX (which mobile clients open in Drive app)."""
        if self._archive_index_cache is not None:
            return self._archive_index_cache
        archives: dict[tuple[str, str], str] = {}
        archive_root = getattr(self.settings, "FOLDER_EMAIL_ARCHIVES", None)
        if not isinstance(archive_root, str) or not archive_root:
            self._archive_index_cache = archives
            return archives
        try:
            files = self.drive.walk(archive_root)
        except Exception as e:
            logger.warning(f"Email Archives walk failed: {e}")
            self._archive_index_cache = archives
            return archives
        if not isinstance(files, list):
            self._archive_index_cache = archives
            return archives
        for f in files:
            if not isinstance(f, dict):
                continue
            name = f.get("name", "")
            if not isinstance(name, str):
                continue
            m = ARCHIVE_FILENAME_RE.match(name)
            if m:
                archives[(m.group(1), m.group(2))] = f.get("id", "")
        self._archive_index_cache = archives
        return archives

    def update_summary(self, docx_id: str, tldr: str,
                       html_id: str | None = None) -> str | None:
        """Append/update an entry in __summaries.json. Called by main.py
        after each daily upload so future runs can show this article in
        their related section with a real summary + browser link."""
        if not docx_id:
            return None
        summaries = self._load_summaries()
        summaries[docx_id] = {
            "tldr": tldr or "",
            "html_id": html_id or "",
        }
        self._summaries_cache = summaries  # keep in-memory copy fresh
        return self.drive.update_or_create(
            filename=SUMMARIES_FILENAME,
            content=json.dumps(summaries, ensure_ascii=False, indent=2),
            folder_id=self.settings.FOLDER_KNOWLEDGE_BASE,
            mime_type="application/json",
        )

    def collect_articles(self) -> list[dict]:
        """Walk KB and parse every article filename we recognize.
        Result is cached on the instance so a single run can call this
        multiple times (e.g. find_related + rebuild) without re-walking Drive.
        """
        if self._articles_cache is not None:
            return self._articles_cache
        files = self.drive.walk(self.settings.FOLDER_KNOWLEDGE_BASE)
        articles = []
        for f in files:
            if f["name"] == MASTER_INDEX_FILENAME:
                continue
            parsed = _parse_filename(f["name"])
            if not parsed:
                continue
            parts = f["parent_path"].split("/") if f["parent_path"] else []
            pillar = parts[0] if parts else "General"
            cluster = parts[1] if len(parts) > 1 else "General"
            articles.append({
                **parsed,
                "id": f["id"],
                "pillar": pillar,
                "cluster": cluster,
                "filename": f["name"],
            })
        self._articles_cache = articles
        return articles

    def find_related(self, current_topic: dict, limit: int = 3) -> list[dict]:
        """Return up to `limit` articles in the same cluster as the current
        topic (excluding the current one itself). Sorted most-recent first.
        Each entry is enriched with `tldr` (1-line summary) and `html_id`
        (Email Archive HTML file_id) when available — both come from the
        __summaries.json index so older articles missing summaries simply
        fall back to title-only display."""
        cluster = current_topic.get("cluster", "General")
        title = current_topic.get("topic", "").lower()
        articles = self.collect_articles()
        same_cluster = [
            a for a in articles
            if a["cluster"] == cluster and a["title"].lower() != title
        ]
        ranked = sorted(same_cluster, key=lambda a: a["date"], reverse=True)[:limit]
        # Enrich without forcing extra Drive calls when the picks list
        # is empty (dry-run path).
        if ranked:
            summaries = self._load_summaries()
            archives = self._collect_email_archive_ids()
            for a in ranked:
                entry = summaries.get(a["id"], {})
                a["tldr"] = entry.get("tldr", "")
                a["html_id"] = (
                    entry.get("html_id")
                    or archives.get((a["date"], a["title"]))
                    or ""
                )
        return ranked

    @staticmethod
    def render_related_section(related: list[dict]) -> str:
        """Markdown snippet to append at the end of an article. Renders
        each related item as: bold title + level/date metadata, with the
        TL;DR on the next line when available. Link prefers the Email
        Archive HTML (browser-friendly) and falls back to the DOCX when
        no HTML is indexed yet."""
        if not related:
            return ""
        lines = ["", "## 📚 อ่านเพิ่มในชุดเดียวกัน", ""]
        for a in related:
            lines.append(
                f"**[L{a['level']}] {a['title']} — {a['date']}**"
            )
            if a.get("tldr"):
                lines.append(a["tldr"])
            lines.append("")  # blank line separates items
        return "\n".join(lines).rstrip() + "\n"

    def render(self, articles: list[dict]) -> str:
        if not articles:
            return (
                "# 📚 Consultant Academy — Knowledge Base\n\n"
                "_(ยังไม่มีบทความ. รัน pipeline อย่างน้อย 1 ครั้งแล้วลองใหม่)_\n"
            )

        articles_sorted = sorted(articles, key=lambda a: a["date"])

        lines = [
            "# 📚 Consultant Academy — Knowledge Base",
            "",
            f"_อัปเดตอัตโนมัติ: {datetime.now().strftime('%Y-%m-%d')} · "
            f"จำนวนบทความ: {len(articles)}_",
            "",
            "---",
            "",
            "## 🆕 สำหรับคนใหม่ — เริ่มอ่านที่นี่",
            "",
            "อ่าน Level 1 ทั้ง 4 pillars สลับกัน ตามลำดับวันที่ "
            "เมื่อจบ Level 1 จึงเริ่ม Level 2",
            "",
            "| ลำดับ | Pillar | บทความ | วันที่ |",
            "|---|---|---|---|",
        ]

        l1 = [a for a in articles_sorted if a["level"] == 1]
        for i, a in enumerate(l1, 1):
            pillar_short = a["pillar"].split("-", 1)[-1] if "-" in a["pillar"] else a["pillar"]
            lines.append(
                f"| {i} | {pillar_short} | "
                f"[{a['title']}]({_drive_link(a['id'])}) | {a['date']} |"
            )

        lines.extend(["", "---", "", "## 📂 ทั้งหมด แยกตาม Pillar", ""])

        by_pillar: dict[str, list[dict]] = {}
        for a in articles_sorted:
            by_pillar.setdefault(a["pillar"], []).append(a)

        for pillar in sorted(by_pillar.keys()):
            label = PILLAR_LABELS.get(pillar, pillar)
            pillar_articles = by_pillar[pillar]
            lines.append(f"### {label} ({len(pillar_articles)})")
            lines.append("")

            by_cluster: dict[str, list[dict]] = {}
            for a in pillar_articles:
                by_cluster.setdefault(a["cluster"], []).append(a)

            for cluster in sorted(by_cluster.keys()):
                cluster_articles = sorted(by_cluster[cluster], key=lambda a: (a["level"], a["date"]))
                lines.append(f"#### {cluster} ({len(cluster_articles)})")
                lines.append("")
                lines.append("| Level | วันที่ | บทความ |")
                lines.append("|---|---|---|")
                for a in cluster_articles:
                    lines.append(
                        f"| L{a['level']} | {a['date']} | "
                        f"[{a['title']}]({_drive_link(a['id'])}) |"
                    )
                lines.append("")

        return "\n".join(lines)

    def rebuild(self) -> str | None:
        """Walk KB, render index, upload (overwrites prior version)."""
        articles = self.collect_articles()
        md = self.render(articles)
        return self.drive.update_or_create(
            filename=MASTER_INDEX_FILENAME,
            content=md,
            folder_id=self.settings.FOLDER_KNOWLEDGE_BASE,
            mime_type="text/markdown",
        )
