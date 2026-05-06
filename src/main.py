"""
Main orchestrator — runs daily via GitHub Actions.
Flow: Calendar → Research → Expert → Industry → Translator → Designer → Drive
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import Settings
from src.agents.research_agent import ResearchAgent
from src.agents.expert_agent import ExpertAgent
from src.agents.industry_agent import IndustryAgent
from src.agents.translator_agent import TranslatorAgent
from src.agents.designer_agent import DesignerAgent
from src.agents.recap_agent import RecapAgent
from src.integrations.drive_api import DriveAPI
from src.integrations.gemini_client import GeminiClient
from src.integrations.research_cache import ResearchCache
from src.utils.calendar_parser import CalendarParser
from src.utils.cost_tracker import CostTracker
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

PILLAR_FOLDER = {
    "TECHNICAL": "01-Technical-Depth",
    "INDUSTRY":  "02-Industry-Business-Logic",
    "FRAMEWORK": "03-Diagnostic-Frameworks",
    "SOFTSKILL": "04-Soft-Skills-Positioning"
}


def main():
    logger.info("=" * 60)
    logger.info("🚀 PTT NGR ESP — Consultant Academy")
    logger.info(f"📅 {datetime.now().strftime('%A %d %B %Y %H:%M')}")
    logger.info("=" * 60)

    s       = Settings()
    drive   = DriveAPI(s)
    gemini  = GeminiClient(s)
    cache   = ResearchCache(s.RESEARCH_CACHE_TTL_DAYS)
    cost    = CostTracker()

    # 1. Get today's topic from Drive calendar
    raw = drive.download_file(s.CALENDAR_FILE_ID)
    topic = CalendarParser(raw).get_topic(datetime.now())
    if not topic:
        logger.error("❌ No topic for today — check Content-Calendar file in Drive")
        return {"status": "error", "reason": "no_topic"}
    logger.info(f"📌 [{topic['pillar']}] {topic['topic']} | {topic.get('industry')}")

    # 2. Multi-agent pipeline
    research = ResearchAgent(gemini, cache).gather(
        topic["topic"], topic.get("industry"), topic.get("keywords"))
    cost.log("gemini-flash", "research", 1200)

    expert = ExpertAgent(gemini).draft(
        topic["topic"], topic["pillar"], research)
    cost.log("gemini-flash", "expert", 1500)

    industry_ctx = None
    if topic.get("industry") and topic["industry"] not in ["General", "ทั่วไป"]:
        industry_ctx = IndustryAgent(gemini).contextualize(
            topic["topic"], topic["industry"], expert)
        cost.log("gemini-flash", "industry", 1000)

    translated = TranslatorAgent(gemini).simplify(
        expert, industry_ctx, topic["topic"], topic["pillar"])
    cost.log("gemini-flash", "translator", 1500)

    email_html = DesignerAgent.create_email(translated, topic)

    # 3. Upload to Drive
    date_str   = topic["date"].strftime("%Y-%m-%d")
    month_path = topic["date"].strftime("%Y/%B").lower()

    email_folder = drive.get_or_create_folder(
        f"Email Archives/{month_path}", s.FOLDER_EMAIL_ARCHIVES)
    drive.upload(
        f"[Email] {date_str} {topic['topic']}.html",
        email_html, email_folder, "text/html")

    if topic["pillar"] != "RECAP":
        pillar_folder = drive.get_or_create_folder(
            f"{PILLAR_FOLDER.get(topic['pillar'], 'General')}/{topic['topic'][:40]}",
            s.FOLDER_KNOWLEDGE_BASE)
        drive.upload(
            f"{date_str} — {topic['pillar']} — {topic['topic'][:50]}.docx",
            translated, pillar_folder,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # 4. Friday recap
    if datetime.now().weekday() == 4:
        logger.info("📋 Friday — generating weekly recap...")
        RecapAgent(gemini, drive, s).generate_and_upload()

    daily_cost = cost.daily_total()
    logger.info(f"💰 Daily cost: ${daily_cost:.4f}")
    logger.info("✅ DONE")

    return {"status": "success", "topic": topic["topic"],
            "pillar": topic["pillar"], "cost_usd": daily_cost}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
