"""
Email the owner when the daily workflow fails.

Run by the `if: failure()` step in daily-routine.yml:
  python src/notify_failure.py run.log

Sends only to ALERT_EMAIL (never the team list), with the error line, the
log tail and a link to the run. Always exits 0 so a broken alert cannot
hide the original failure.
"""
import html
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.email_sender import send_daily_email  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

logger = setup_logger(__name__) if __name__ == "__main__" else logging.getLogger(__name__)

TAIL_LINES = 20
# Last line of a Python traceback: "pkg.module.SomeError: message".
_ERROR_LINE_RE = re.compile(r"^[\w.]*(?:Error|Exception)\b.*$", re.MULTILINE)


def build_alert(log_text: str, run_url: str) -> tuple[str, str]:
    errors = _ERROR_LINE_RE.findall(log_text or "")
    reason = errors[-1] if errors else "ไม่พบข้อความ error ใน log (อาจล้มเหลวก่อนเริ่ม pipeline)"
    tail = "\n".join((log_text or "").strip().splitlines()[-TAIL_LINES:]) or "(ไม่มี log)"
    subject = "⚠️ Consultant Academy: run ล้มเหลว — อีเมลวันนี้ไม่ได้ส่งถึงทีม"
    body = (
        "<p><b>Daily routine ล้มเหลว</b> — ระบบไม่ได้ส่งอีเมลที่มีปัญหาออกไปหาทีม</p>"
        f"<p><b>สาเหตุ:</b> <code>{html.escape(reason[:500])}</code></p>"
        f'<p><a href="{html.escape(run_url)}">เปิด run บน GitHub Actions</a>'
        " — กด Re-run jobs ได้เมื่อแก้แล้ว</p>"
        f"<p><b>Log {TAIL_LINES} บรรทัดสุดท้าย:</b></p>"
        f'<pre style="font-size:12px;white-space:pre-wrap">{html.escape(tail)}</pre>'
    )
    return subject, body


def main(log_path: str = "run.log") -> int:
    to = [a.strip() for a in os.getenv("ALERT_EMAIL", "").split(",") if a.strip()]
    if not to:
        logger.info("🔕 ALERT_EMAIL not set — skipping failure alert")
        return 0
    path = Path(log_path)
    log_text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    subject, body = build_alert(log_text, os.getenv("RUN_URL", ""))
    ok = send_daily_email(subject, body, recipients=to)
    logger.info(f"🚨 Failure alert {'sent' if ok else 'NOT sent'} to {len(to)} address(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "run.log"))
