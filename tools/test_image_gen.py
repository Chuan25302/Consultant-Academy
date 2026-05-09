"""
Standalone tester for the daily pipeline's image agent.

Reads an article (markdown) and a topic, runs it through the same
ImageAgent that the daily pipeline uses, saves the result(s) to
test_images/ for visual review. Does NOT touch the daily pipeline or
upload to Drive.

Defaults to Imagen 4 (best Thai text rendering as of mid-2026); set
the IMAGE_MODEL env var to A/B-test alternatives such as
gemini-2.5-flash-image without code changes.

Usage:
  # quick run with built-in TCO sample (uses model from IMAGE_MODEL env)
  python tools/test_image_gen.py

  # try a different model for one run
  IMAGE_MODEL=gemini-2.5-flash-image python tools/test_image_gen.py

  # use a real article file (markdown)
  python tools/test_image_gen.py --md path/to/article.md \
      --topic "TCO Analysis Framework" --industry "Manufacturing"

  # generate 3 variants in one go (cost = 3x)
  python tools/test_image_gen.py --n 3

  # print the assembled image prompt without calling the API (free)
  python tools/test_image_gen.py --prompt-only

Pricing (Vertex AI, 2026):
  imagen-4.0-generate-001       $0.04   / image (1024x1024)
  imagen-4.0-fast-generate-001  $0.02   / image
  imagen-4.0-ultra-generate-001 $0.06   / image
  gemini-2.5-flash-image        $0.039  / image

Auth: reuses the same VERTEX_AI_PROJECT + service account used by the
daily pipeline. Make sure .env has:
  VERTEX_AI_PROJECT=...
  VERTEX_AI_LOCATION=us-central1
  VERTEX_AI_SERVICE_ACCOUNT_FILE=vertex-ai-service-key.json
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.agents.image_agent import IMAGE_PROMPT, ImageAgent  # noqa: E402
from src.config.settings import Settings  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "test_images"
OUTPUT_DIR.mkdir(exist_ok=True)

# Best-effort cost per image for the most common Vertex AI image models.
# Falls back to 0.04 for any unknown model.
COST_BY_MODEL = {
    "imagen-4.0-generate-001":       0.04,
    "imagen-4.0-fast-generate-001":  0.02,
    "imagen-4.0-ultra-generate-001": 0.06,
    "imagen-3.0-generate-002":       0.04,
    "gemini-2.5-flash-image":        0.039,
}

SAMPLE_TOPIC = "Total Cost of Ownership (TCO) Analysis Framework"
SAMPLE_INDUSTRY = "โรงงานผลิตเครื่องดื่ม"
SAMPLE_ARTICLE = """## ประเด็นวันนี้
TCO เปลี่ยน conversation จาก "ราคาถูกสุด" เป็น "มูลค่ารวม 10 ปี" — ลดการแข่งขันด้านราคา ขยับไปสู่การขายมูลค่าจริงที่จับต้องได้

## 1. TCO ในมุมมอง Consultant
ลูกค้าต้องการมูลค่ารวมระยะยาว ไม่ใช่แค่ราคาถูก TCO เปิดเผยต้นทุนแฝงตลอดอายุการใช้งาน

## 2. Case Study
**Situation:** โรงงานเครื่องดื่มขนาดกลาง อายุระบบ 15+ ปี ค่าไฟเฉลี่ย 3.5 ล้านบาท/เดือน
ค่าบำรุงรักษาฉุกเฉินกว่า 5 แสนบาท/ปี

**Complication:** ลูกค้ามองแค่ CapEx ไม่เห็นต้นทุนแฝงจาก downtime + maintenance + ESG impact

**Result:** ลงทุน 25 ล้านบาท ลดค่าไฟ 25-30% (≈1 ล้านบาท/เดือน) ลดบำรุงรักษา 70% คืนทุน 3-4 ปี

## 3. Consultant Move
ลองถามลูกค้า: "ในรอบ 12 เดือนที่ผ่านมา ระบบนี้เคย downtime กี่ชั่วโมง?
ค่าเสียโอกาสต่อชั่วโมงเท่าไหร่?"

## 5. Knowledge Capture
- TCO = CapEx + Σ(OpEx_n × (1+escalation)^n / (1+r)^n) ตลอด N ปี
- Payback rule of thumb: < ½ ของอายุการใช้งาน
- Downtime cost: ค่าเสียโอกาส/ชั่วโมง × downtime hours
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default=SAMPLE_TOPIC)
    parser.add_argument("--industry", default=SAMPLE_INDUSTRY)
    parser.add_argument("--pillar", default="FRAMEWORK")
    parser.add_argument("--md", type=Path, help="path to article markdown")
    parser.add_argument("--n", type=int, default=1,
                        help="number of variations to generate")
    parser.add_argument("--prompt-only", action="store_true",
                        help="print assembled prompt without hitting the API")
    args = parser.parse_args()

    article = args.md.read_text(encoding="utf-8") if args.md else SAMPLE_ARTICLE

    if args.prompt_only:
        # Single-step pipeline now: the article goes straight into the
        # image prompt, no separate brief generator call.
        filled = IMAGE_PROMPT.format(article=article[:6000])
        print("=" * 70)
        print("IMAGE PROMPT (sent directly to image model):")
        print("=" * 70)
        print(filled)
        print()
        print(f"[prompt length: {len(filled)} chars, ~{len(filled)//3} tokens]")
        return

    settings = Settings()
    agent = ImageAgent(settings)

    if not agent.client:
        sys.exit(
            "Vertex AI not configured — set VERTEX_AI_PROJECT and "
            "VERTEX_AI_SERVICE_ACCOUNT_FILE in .env."
        )

    topic_meta = {
        "topic": args.topic,
        "industry": args.industry,
        "pillar": args.pillar,
    }

    model = agent.model_name
    cost_per = COST_BY_MODEL.get(model, 0.04)
    safe_model = model.replace("/", "_").replace(":", "_")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Model:    {model}")
    print(f"Variants: {args.n}")
    print(f"Cost:     ${cost_per:.3f} x {args.n} = ${cost_per * args.n:.3f}")
    print()

    for i in range(1, args.n + 1):
        print(f"[{i}/{args.n}] generating...")
        t0 = time.time()
        data = agent.generate(article, topic_meta)
        elapsed = time.time() - t0
        if not data:
            print(f"  failed (took {elapsed:.1f}s)")
            continue
        suffix = f"_v{i}" if args.n > 1 else ""
        out = OUTPUT_DIR / f"{timestamp}_{safe_model}{suffix}.png"
        out.write_bytes(data)
        print(f"  saved: {out.relative_to(Path.cwd())}  ({len(data)//1024} KB, {elapsed:.1f}s)")

    print(f"\nImage gen cost (Vertex billing console): ~${cost_per * args.n:.3f}")


if __name__ == "__main__":
    main()
