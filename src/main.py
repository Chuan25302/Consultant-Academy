"""
Main orchestrator — runs daily via GitHub Actions.
Flow: Calendar → Research → Expert → Industry → Translator → Designer → Drive
RECAP days short-circuit straight to RecapAgent (skipping the full pipeline).

CLI:
  python src/main.py                       # today's topic
  python src/main.py --date 2024-05-06     # backfill specific day
  python src/main.py --recap-only          # force weekly recap now
  python src/main.py --plan-next           # extend calendar by 4 weeks now
  python src/main.py --dry-run             # skip Drive uploads
  python src/main.py --skip-validation     # bypass startup pre-flight check
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.agents.designer_agent import DesignerAgent
from src.agents.editor_agent import EditorAgent
from src.agents.expert_agent import ExpertAgent
from src.agents.factchecker_agent import FactCheckerAgent
from src.agents.image_agent import ImageAgent
from src.agents.industry_agent import IndustryAgent
from src.agents.planner_agent import CalendarPlannerAgent
from src.agents.recap_agent import RecapAgent
from src.agents.research_agent import ResearchAgent
from src.agents.translator_agent import TranslatorAgent
from src.config.settings import Settings, now_bangkok
from src.integrations.drive_api import DriveAPI
from src.integrations.gemini_client import GeminiClient
from src.integrations.research_cache import ResearchCache
from src.utils.calendar_parser import CalendarParser
from src.utils.cli import parse_date, validate_startup
from src.utils.cost_tracker import CostTracker
from src.utils.docx_writer import markdown_to_docx_bytes
from src.utils.index_builder import IndexBuilder
from src.utils.email_sender import send_daily_email
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

PILLAR_FOLDER = {
    "TECHNICAL":      "01-Technical-Depth",
    "INDUSTRY":       "02-Industry-Business-Logic",
    "FRAMEWORK":      "03-Diagnostic-Frameworks",
    "SOFTSKILL":      "04-Soft-Skills-Positioning",
    "COMPLIANCE":     "05-Standards-Compliance",
    "SUSTAINABILITY": "06-Sustainability-Carbon",
}

WEEKDAY_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"]

MONTHS_TH = {
    1:"มกราคม", 2:"กุมภาพันธ์", 3:"มีนาคม", 4:"เมษายน",
    5:"พฤษภาคม", 6:"มิถุนายน", 7:"กรกฎาคม", 8:"สิงหาคม",
    9:"กันยายน", 10:"ตุลาคม", 11:"พฤศจิกายน", 12:"ธันวาคม",
}

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def main(date: str = None, dry_run: bool = False,
         recap_only: bool = False, plan_next: bool = False,
         skip_validation: bool = False):
    target = parse_date(date) if date else now_bangkok()
    logger.info("=" * 60)
    logger.info("🚀 PTT NGR ESP — Consultant Academy")
    logger.info(f"📅 {target.strftime('%A %d %B %Y %H:%M')} (Asia/Bangkok)")
    if dry_run:
        logger.info("🧪 DRY RUN — no Drive uploads will occur")
    if recap_only:
        logger.info("📋 RECAP-ONLY mode")
    logger.info("=" * 60)

    s      = Settings()
    cost   = CostTracker()
    drive  = DriveAPI(s)
    gemini = GeminiClient(s, cost_tracker=cost)
    cache  = ResearchCache(s.RESEARCH_CACHE_TTL_DAYS)

    if not skip_validation:
        logger.info("🔎 Validating Drive access...")
        validate_startup(s, drive)

    if plan_next:
        logger.info("📅 PLAN-NEXT mode — extending calendar")
        raw = drive.download_file(s.CALENDAR_FILE_ID)
        if not raw:
            logger.error("❌ Calendar file empty or unreadable")
            return {"status": "error", "reason": "calendar_unreadable"}
        ok = CalendarPlannerAgent(gemini, drive, s).force_extend(
            raw, dry_run=dry_run)
        return {"status": "success" if ok else "error",
                "mode": "plan_only", "extended": ok,
                "cost_usd": cost.daily_total()}

    if recap_only:
        RecapAgent(gemini, drive, s).generate_and_upload(today=target, dry_run=dry_run)
        daily_cost = cost.daily_total()
        logger.info(f"💰 Daily cost: ${daily_cost:.4f}")
        return {"status": "success", "mode": "recap_only", "cost_usd": daily_cost}

    raw = drive.download_file(s.CALENDAR_FILE_ID)
    if not raw:
        logger.error("❌ Calendar file empty or unreadable")
        return {"status": "error", "reason": "calendar_unreadable"}

    topic = CalendarParser(raw).get_topic(target)

    # Self-healing: missing topic should not kill the run.
    # Saturday → RECAP fallback (no LLM cost). Mon–Fri → auto-extend + retry.
    if not topic:
        date_str = target.strftime("%Y-%m-%d")
        if target.weekday() == 5:  # Saturday
            week_num = target.isocalendar().week
            logger.warning(f"⚠️ No topic for {date_str} (Saturday) — defaulting to RECAP")
            topic = {
                "pillar": "RECAP",
                "topic": f"สรุปสัปดาห์ที่ {week_num}",
                "industry": "General",
                "keywords": ["recap"],
                "cluster": "General",
                "level": 1,
                "date": target,
            }
        elif not dry_run:
            logger.warning(f"⚠️ No topic for {date_str} — auto-extending calendar")
            try:
                extended = CalendarPlannerAgent(gemini, drive, s).force_extend(raw)
            except Exception as e:
                logger.error(f"Auto-extend failed: {e}")
                extended = False
            if extended:
                raw = drive.download_file(s.CALENDAR_FILE_ID)
                topic = CalendarParser(raw).get_topic(target) if raw else None
        if not topic:
            logger.error(f"❌ No topic for {target.strftime('%Y-%m-%d')}")
            return {"status": "error", "reason": "no_topic"}
    logger.info(f"📌 [{topic['pillar']}] {topic['topic']} | {topic.get('industry')}")

    if topic["pillar"] == "RECAP":
        logger.info("📋 RECAP day — generating weekly recap...")
        RecapAgent(gemini, drive, s).generate_and_upload(today=target, dry_run=dry_run)
        daily_cost = cost.daily_total()
        logger.info(f"💰 Daily cost: ${daily_cost:.4f}")
        return {"status": "success", "topic": topic["topic"],
                "pillar": "RECAP", "cost_usd": daily_cost}

    research = ResearchAgent(gemini, cache).gather(
        topic["topic"], topic.get("industry"), topic.get("keywords"))
    expert = ExpertAgent(gemini).draft(
        topic["topic"], topic["pillar"], research,
        industry=topic.get("industry", "ทั่วไป"),
        topic_meta=topic)

    industry_ctx = None
    if topic.get("industry") and topic["industry"] not in ["General", "ทั่วไป"]:
        industry_ctx = IndustryAgent(gemini).contextualize(
            topic["topic"], topic["industry"], expert)

    # FactChecker: anti-hallucination gate. Reviews technical+industry content
    # against the original research data; softens unverifiable claims.
    combined_technical = expert
    if industry_ctx:
        combined_technical = f"{expert}\n\n## บริบทอุตสาหกรรม\n{industry_ctx}"
    verified = FactCheckerAgent(gemini).review(combined_technical, research)

    translated = TranslatorAgent(gemini).simplify(
        verified, None, topic["topic"], topic["pillar"])

    edited = EditorAgent(gemini).review(translated)

    index = IndexBuilder(drive, s)
    final_md = edited

    # Optional infographic (gated on FOLDER_IMAGES + Vertex AI). Failures
    # are non-blocking — if image gen errors out we still send the email.
    image_bytes = None
    if s.FOLDER_IMAGES and s.use_vertex:
        image_bytes = ImageAgent(s).generate(final_md, topic)

    # Two HTMLs from the same content:
    # - email_html uses cid:infographic so the image is MIME-attached
    #   (downloadable + inline-rendered without bloating the body).
    # - archive_html embeds base64 so opening the archived HTML later
    #   from Drive still shows the image standalone.
    image_cid = "infographic" if image_bytes else None
    email_html = DesignerAgent.create_email(final_md, topic, image_cid=image_cid)
    archive_html = DesignerAgent.create_email(final_md, topic, image_bytes=image_bytes)

    date_str   = topic["date"].strftime("%Y-%m-%d")
    month_path = topic["date"].strftime("%Y/%B").lower()
    level      = topic.get("level", 1)
    cluster    = topic.get("cluster", "General")
    pillar_dir = PILLAR_FOLDER.get(topic["pillar"], "General")

    email_filename = f"[Email] {date_str} {topic['topic']}.html"
    docx_filename  = f"[L{level}] {date_str} {topic['topic'][:50]}.docx"

    weekday_th = WEEKDAY_TH[topic["date"].weekday()]
    subject_date = topic["date"].strftime("%Y-%m-%d")
    subject = f"[{subject_date} · {topic['pillar']} · {weekday_th}] {topic['topic']}"

    if dry_run:
        logger.info(f"🧪 [dry-run] would upload: {email_filename}")
        logger.info(f"🧪 [dry-run] would upload: {pillar_dir}/{cluster}/{docx_filename}")
        if image_bytes:
            logger.info(f"🧪 [dry-run] would upload image ({len(image_bytes)//1024} KB)")
        logger.info("🧪 [dry-run] would rebuild Knowledge Base master index")
        logger.info(f"🧪 [dry-run] would send email: {subject}")
    else:
        # Upload infographic first so the file is in Drive even if email
        # delivery fails downstream.
        if image_bytes and s.FOLDER_IMAGES:
            img_folder = drive.get_or_create_folder(
                f"Images/{month_path}", s.FOLDER_IMAGES)
            img_filename = f"[Image] {date_str} {topic['topic'][:50]}.png"
            drive.upload(img_filename, image_bytes, img_folder, "image/png")

        # Upload the standalone-viewable archive copy (image embedded
        # as base64) so Drive preview renders it correctly later. The
        # SMTP delivery uses the cid version below.
        email_folder = drive.get_or_create_folder(
            f"Email Archives/{month_path}", s.FOLDER_EMAIL_ARCHIVES)
        html_id = drive.upload(email_filename, archive_html, email_folder, "text/html")

        kb_folder = drive.get_or_create_folder(
            f"{pillar_dir}/{cluster}", s.FOLDER_KNOWLEDGE_BASE)
        docx_subtitle = (
            f"L{level} · {cluster}" if cluster and cluster != "General"
            else f"L{level}"
        )
        d = topic["date"]
        docx_date = f"{d.day} {MONTHS_TH[d.month]} {d.year + 543}"
        docx_bytes = markdown_to_docx_bytes(
            final_md,
            title=topic["topic"],
            pillar=topic["pillar"],
            subtitle=docx_subtitle,
            date=docx_date,
            image_bytes=image_bytes,
        )
        docx_id = drive.upload(docx_filename, docx_bytes, kb_folder, DOCX_MIME)

        # Persist this article's TL;DR + Email Archive HTML id so future
        # daily emails can show a real summary line under the related
        # "อ่านเพิ่มในชุดเดียวกัน" link instead of a bare title.
        if docx_id:
            tldr = DesignerAgent._extract_tldr(final_md)
            try:
                index.update_summary(docx_id, tldr, html_id)
            except Exception as e:
                logger.warning(f"update_summary failed (non-blocking): {e}")

        logger.info("📚 Rebuilding Knowledge Base master index...")
        index.rebuild()

        attachments = None
        if image_bytes:
            # Recipient sees the file in their attachment area AND the
            # cid-referenced <img> in the body resolves to the same data.
            img_attach_name = f"infographic-{date_str}.png"
            attachments = [(img_attach_name, image_bytes, image_cid)]

        email_ok = send_daily_email(subject, email_html, attachments=attachments)
        if not email_ok:
            logger.warning("📧 Email not sent — check EMAIL_SENDER/APP_PASSWORD/RECIPIENTS")

        # Auto-extend calendar if running low (non-blocking — failures are
        # logged but don't fail today's run since today's content already
        # uploaded successfully)
        try:
            CalendarPlannerAgent(gemini, drive, s).maybe_extend(raw, target)
        except Exception as e:
            logger.error(f"Planner failed (non-blocking): {e}")

    daily_cost = cost.daily_total()
    logger.info(f"💰 Daily cost: ${daily_cost:.4f}")
    logger.info("✅ DONE")
    sys.stdout.flush()

    return {"status": "success", "topic": topic["topic"],
            "pillar": topic["pillar"], "cost_usd": daily_cost}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PTT NGR ESP Consultant Academy")
    parser.add_argument("--date", help="YYYY-MM-DD override (defaults to today, Bangkok TZ)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run pipeline but skip Drive uploads")
    parser.add_argument("--recap-only", action="store_true",
                        help="Skip the daily pipeline and just run the weekly recap")
    parser.add_argument("--plan-next", action="store_true",
                        help="Skip pipeline; extend calendar by 4 weeks (Pro 2.5)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Bypass Drive access pre-flight check")
    args = parser.parse_args()

    result = main(
        date=args.date,
        dry_run=args.dry_run,
        recap_only=args.recap_only,
        plan_next=args.plan_next,
        skip_validation=args.skip_validation,
    )
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    sys.exit(0 if result.get("status") == "success" else 1)
