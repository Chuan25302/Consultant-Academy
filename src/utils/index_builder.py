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
"""
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

MASTER_INDEX_FILENAME = "00-Master-Index.md"

PILLAR_LABELS = {
    "01-Technical-Depth":         "TECHNICAL — เนื้อหาเทคนิค",
    "02-Industry-Business-Logic": "INDUSTRY — ตามอุตสาหกรรม",
    "03-Diagnostic-Frameworks":   "FRAMEWORK — กรอบการวิเคราะห์",
    "04-Soft-Skills-Positioning": "SOFTSKILL — ทักษะที่ปรึกษา",
    "05-Standards-Compliance":    "COMPLIANCE — มาตรฐาน/การปฏิบัติตามกฎ",
}

# [L1] 2024-05-06 Topic.docx
NEW_FILENAME_RE = re.compile(
    r"^\[L(\d+)\]\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\.[a-z]+$"
)
# 2024-05-06 — TECHNICAL — Topic.docx (legacy)
OLD_FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+[—-]\s+\w+\s+[—-]\s+(.+?)\.[a-z]+$"
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
        topic (excluding the current one itself). Sorted most-recent first."""
        cluster = current_topic.get("cluster", "General")
        title = current_topic.get("topic", "").lower()
        articles = self.collect_articles()
        same_cluster = [
            a for a in articles
            if a["cluster"] == cluster and a["title"].lower() != title
        ]
        return sorted(same_cluster, key=lambda a: a["date"], reverse=True)[:limit]

    @staticmethod
    def render_related_section(related: list[dict]) -> str:
        """Markdown snippet to append at the end of an article."""
        if not related:
            return ""
        lines = ["", "## 📚 อ่านเพิ่มในชุดเดียวกัน", ""]
        for a in related:
            link = _drive_link(a["id"])
            lines.append(f"- [L{a['level']}] [{a['title']}]({link}) — {a['date']}")
        return "\n".join(lines)

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
