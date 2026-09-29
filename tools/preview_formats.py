"""Dry-run one article per pillar and report the shape of each result.

Usage: python tools/preview_formats.py <output_dir>
Sends nothing, uploads nothing: it calls main(date=..., dry_run=True) once
per calendar date (main() picks the topic by DATE, so six different pillars
need six different dates) and captures the HTML that would have been emailed.
Run log is written to <output_dir>/run.log.
"""
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")

import src.main as m  # noqa: E402
from src.config.settings import Settings, now_bangkok  # noqa: E402
from src.integrations.drive_api import DriveAPI  # noqa: E402
from src.utils.calendar_parser import CalendarParser  # noqa: E402

WANTED = ["TECHNICAL", "INDUSTRY", "FRAMEWORK",
          "SOFTSKILL", "COMPLIANCE", "SUSTAINABILITY"]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def pick_dates(raw: str, today: datetime) -> list[tuple[str, str]]:
    """Earliest calendar date on/after today for each distinct pillar."""
    parser = CalendarParser(raw)
    seen: dict[str, str] = {}
    for d in sorted(set(DATE_RE.findall(raw))):
        if d < today.strftime("%Y-%m-%d"):
            continue
        topic = parser.get_topic(datetime.strptime(d, "%Y-%m-%d"))
        if topic and topic["pillar"] not in seen:
            seen[topic["pillar"]] = d
    ordered = [p for p in WANTED if p in seen] + [p for p in seen if p not in WANTED]
    return [(seen[p], p) for p in ordered[:6]]


def main(outdir: str) -> int:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(out / "run.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(fh)

    s = Settings()
    raw = DriveAPI(s).download_file(s.CALENDAR_FILE_ID)
    if not raw:
        print("calendar unreadable")
        return 1
    plan = pick_dates(raw, now_bangkok())
    print("plan:", plan)

    original = m.DesignerAgent.create_email
    captured: dict[str, str] = {}

    def capture(content, metadata, *a, **kw):
        html = original(content, metadata, *a, **kw)
        if "image_bytes" in kw:
            captured[metadata["date"].strftime("%Y-%m-%d")] = html
        return html

    m.DesignerAgent.create_email = staticmethod(capture)
    failures: dict[str, str] = {}
    for date, pillar in plan:
        print(f"--- {date} {pillar}")
        try:
            m.main(date=date, dry_run=True, skip_validation=True)
        except Exception as e:  # noqa: BLE001 - a failed pillar is a result
            failures[date] = f"{type(e).__name__}: {e}"

    print(f"\n{'date':10s} {'pillar':15s} {'words':>6s} {'kit':>4s} "
          f"{'recall':>6s} {'box':>4s} {'bad':>4s}")
    for date, pillar in plan:
        html = captured.get(date)
        if html is None:
            print(f"{date:10s} {pillar:15s} FAILED {failures.get(date, 'no html captured')}")
            continue
        text = re.sub(r"<[^>]+>", " ", html)
        (out / f"{date}_{pillar}.html").write_text(html, encoding="utf-8")
        has_kit = 'class="kit"' in html
        has_recall = 'class="recall"' in html
        boxes = text.count("☐")
        bad = "[Error" in text or "$\\" in text
        print(f"{date:10s} {pillar:15s} {len(text.split()):6d} "
              f"{'yes' if has_kit else 'NO':>4s} "
              f"{'yes' if has_recall else 'no':>6s} {boxes:4d} "
              f"{'BAD' if bad else 'ok':>4s}")
    return 1 if failures or len(captured) < len(plan) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
