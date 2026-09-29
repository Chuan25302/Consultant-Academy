# Per-Pillar Email Format Profiles + Retention Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each daily email teach one transferable idea in a shape that varies by pillar, ship one usable artifact, and ask the reader to recall older material — without adding an LLM call or lengthening the email.

**Architecture:** A data-only registry (`src/agents/formats.py`) holds one profile per pillar: middle sections, kit type, and a scene pool. `TranslatorAgent` assembles its prompt from that profile plus the topic's level and two recall items pulled from the existing `__summaries.json` rail. `EditorAgent` enforces the result with deterministic gates; `DesignerAgent` renders two new boxes. The Saturday recap flips from summary to retrieval.

**Tech Stack:** Python 3.11, google-genai (Vertex `global`, `gemini-3.8-flash`), python-markdown + premailer, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-29-email-format-profiles-design.md` — v2, as amended by A1–A9. Read the amendments before any task; they supersede the v1 sections they name.

## Global Constraints

- **Anchor contract — never rename, never drop:** `## 💡 ประเด็นวันนี้`, `Consultant Move`, `Knowledge Capture`, `## 📖 ศัพท์น่ารู้`. `designer_agent.py:41-70` and `recap_agent.py` parse them.
- **No new LLM calls.** Recall questions are produced inside the existing translator call (spec NOTE, seat 6).
- **Length targets (A5):** body 600–700 words, kit ~150, recall ~80.
- **Checklists use `- ☐ `**, never `- [ ]` — python-markdown leaves `[ ]` as literal text (`designer_agent.py:235`).
- **No `<details>`, no JS (A9).** Answers render in a separate box at the bottom.
- **Every reference number in a kit carries `— ที่มา: <source>` (A7).**
- **Recall is best-effort (C3):** any Drive/summaries failure omits the block; it is never an error.
- **`formats.py` is data-only** — no logic, so a profile edit cannot break assembly (seat 6 MINOR).
- **Existing rules stay:** no greeting/self-intro/tagline, dash bullets only, no LaTeX, source-numbers-first, no real company names.
- Run `python -m pytest -q` and `ruff check .` before every commit.

---

### Task 1: Format profile registry

**Files:**
- Create: `src/agents/formats.py`
- Test: `tests/test_formats.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Profile` (frozen dataclass: `sections: tuple[tuple[str, str], ...]`, `kit: str`, `scenes: tuple[str, ...]`), `FORMAT_PROFILES: dict[str, Profile]`, `KIT_SPECS: dict[str, KitSpec]` (`KitSpec` frozen dataclass: `label: str`, `instructions: str`), `LEVEL_GUIDE: dict[int, str]`, `profile_for(pillar: str) -> Profile`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_formats.py
import pytest

from src.agents.formats import (FORMAT_PROFILES, KIT_SPECS, LEVEL_GUIDE,
                                profile_for)

PILLARS = ["TECHNICAL", "INDUSTRY", "FRAMEWORK",
           "SOFTSKILL", "COMPLIANCE", "SUSTAINABILITY"]


@pytest.mark.parametrize("pillar", PILLARS)
def test_every_pillar_has_a_complete_profile(pillar):
    p = FORMAT_PROFILES[pillar]
    assert len(p.sections) == 2, "two middle sections per issue (A2)"
    assert all(title and intent for title, intent in p.sections)
    assert p.kit in KIT_SPECS
    assert len(p.scenes) >= 5, "scene pool must allow no-repeat rotation"


def test_no_two_pillars_share_a_section_title():
    titles = [t for p in FORMAT_PROFILES.values() for t, _ in p.sections]
    assert len(titles) == len(set(titles)), "identical titles re-create the sameness"


def test_all_three_kits_are_used_by_some_pillar():
    used = {p.kit for p in FORMAT_PROFILES.values()}
    assert used == set(KIT_SPECS)


def test_level_guide_covers_l1_l2_l3():
    assert set(LEVEL_GUIDE) == {1, 2, 3}
    assert all(len(v) > 20 for v in LEVEL_GUIDE.values())


def test_unknown_pillar_falls_back_to_technical():
    assert profile_for("NOPE") is FORMAT_PROFILES["TECHNICAL"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_formats.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.agents.formats'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agents/formats.py
"""
Per-pillar email format profiles (spec 2026-09-29, A2/A6).

Data only — no logic lives here, so editing a profile cannot break prompt
assembly. TranslatorAgent reads these; EditorAgent enforces the result.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class KitSpec:
    label: str
    instructions: str


@dataclass(frozen=True)
class Profile:
    sections: tuple[tuple[str, str], ...]
    kit: str
    scenes: tuple[str, ...]


KIT_SPECS = {
    "checklist": KitSpec(
        label="Checklist เดินหน้างาน",
        instructions=(
            "6–8 ข้อ ขึ้นต้นด้วย '- ☐ ' (ห้ามใช้ '- [ ]')\n"
            "แต่ละข้อต้องครบ 3 ส่วน: ตรวจอะไร / ค่าปกติควรเป็นเท่าไร (ตัวเลข+หน่วย) / "
            "ถ้าผิดปกติแปลว่าอะไร\n"
            "อย่างน้อย 3 ข้อต้องมีตัวเลข+หน่วย"
        ),
    ),
    "questions": KitSpec(
        label="ชุดคำถามเจาะลูกค้า",
        instructions=(
            "4–5 คำถาม เรียงจากกว้างไปลึก แต่ละบรรทัดลงท้ายด้วย '?'\n"
            "ตามด้วย objection ที่เจอบ่อย 2 ข้อ รูปแบบ:\n"
            "**ลูกค้า:** \"...\"\n**ตอบ:** \"...\"\n"
            "คำตอบต้องอ้างตัวเลขหรือความเสี่ยงที่จับต้องได้"
        ),
    ),
    "calculator": KitSpec(
        label="สูตรคำนวณพร้อมใช้",
        instructions=(
            "สูตร 1–2 บรรทัด เขียนเป็นข้อความธรรมดา (ห้าม LaTeX) มีเครื่องหมาย '='\n"
            "ระบุตัวแปรที่ต้องถามลูกค้า\n"
            "ตัวเลขอ้างอิงทุกตัวต้องมี '— ที่มา: ...' ต่อท้าย\n"
            "ปิดท้ายด้วยตัวอย่างแทนค่าจริง 1 ชุด"
        ),
    ),
}

LEVEL_GUIDE = {
    1: "L1 — พบครั้งแรก: นิยามศัพท์ให้ชัด ยกตัวอย่างเดียวที่เห็นภาพ ไม่ต้องลงลึกข้อยกเว้น",
    2: "L2 — เอาไปใช้: ต้องมีตัวอย่างคำนวณหรือขั้นตอนที่ทำตามได้จริงพร้อมตัวเลข",
    3: "L3 — ตัดสินใจเป็น: เน้น trade-off ว่าเลือกอะไรแลกอะไร และกรณีที่วิธีนี้ใช้ไม่ได้",
}

_SCENES_PLANT = ("โรงงานอาหารแช่แข็ง", "โรงงานกระดาษ", "โรงงานชิ้นส่วนยานยนต์",
                 "โรงงานสิ่งทอ", "โรงงานเซรามิก", "โรงงานยางแปรรูป")
_SCENES_BUILDING = ("โรงพยาบาล 24 ชั่วโมง", "โรงแรมริมทะเล", "อาคารสำนักงานให้เช่า",
                    "ศูนย์การค้าชุมชน", "ดาต้าเซ็นเตอร์ขนาดกลาง", "คลังสินค้าห้องเย็น")
_SCENES_PEOPLE = ("ฝ่ายจัดซื้อโรงงานชิ้นส่วนยานยนต์", "CFO กลุ่มค้าปลีก",
                  "ผู้รับเหมางานระบบ M&E", "วิศวกรโรงงานกระดาษ",
                  "ผู้จัดการอาคารสำนักงาน", "เจ้าของโรงแรมขนาดกลาง")

FORMAT_PROFILES = {
    "TECHNICAL": Profile(
        sections=(
            ("หน้างานบอกอะไร",
             "อาการหรือค่าที่วัดได้จริงหน้างาน และวิธีอ่านค่านั้นว่าแปลว่าอะไร "
             "เขียนให้ชัดว่าเป็นตัวอย่างประกอบ ไม่ใช่ข้อมูลจากไซต์จริง"),
            ("เคสสั้น: จากอาการสู่ทางแก้",
             "ย่อหน้าเดียว ปัญหา → สิ่งที่ทำ → ผลลัพธ์เป็นตัวเลขพร้อม qualifier"),
        ),
        kit="checklist",
        scenes=_SCENES_PLANT + _SCENES_BUILDING,
    ),
    "INDUSTRY": Profile(
        sections=(
            ("โปรไฟล์ธุรกิจและ Energy Profile",
             "ธุรกิจนี้หาเงินยังไง ต้นทุนพลังงานคิดเป็นสัดส่วนเท่าไร ใช้พลังงานไปกับอะไรมากสุด"),
            ("สามจุดปวดที่ขายได้",
             "จุดปวด 3 ข้อ แต่ละข้อมีสัญญาณที่สังเกตได้ตอนเดินดูหน้างาน"),
        ),
        kit="questions",
        scenes=_SCENES_BUILDING + _SCENES_PEOPLE,
    ),
    "FRAMEWORK": Profile(
        sections=(
            ("โจทย์ที่กรอบนี้แก้",
             "สถานการณ์ที่ตัดสินใจยากโดยไม่มีกรอบ และกรอบนี้เข้ามาช่วยตรงไหน"),
            ("ลองใช้กับเคสจริงทีละขั้น",
             "worked example เดินทีละขั้นจนได้ข้อสรุป พร้อมตัวเลขประกอบ"),
        ),
        kit="calculator",
        scenes=_SCENES_PEOPLE + _SCENES_PLANT,
    ),
    "SOFTSKILL": Profile(
        sections=(
            ("บทสนทนาจริง",
             "บทสนทนา 4–6 บรรทัดสลับ ลูกค้า/ที่ปรึกษา ใช้ blockquote '> ' ทุกบรรทัด"),
            ("ถอดบทเรียน: ทำไมประโยคนั้นได้ผล",
             "ชี้ว่าประโยคไหนเปลี่ยนทิศบทสนทนา และหลักการเบื้องหลังคืออะไร"),
        ),
        kit="questions",
        scenes=_SCENES_PEOPLE + _SCENES_BUILDING,
    ),
    "COMPLIANCE": Profile(
        sections=(
            ("ข้อกำหนดที่ต้องรู้",
             "ใครต้องทำ ต้องทำอะไร ภายในเมื่อไร อ้างชื่อกฎหมายหรือมาตรฐานให้ตรง"),
            ("ถ้าไม่ทำเกิดอะไร",
             "บทลงโทษหรือต้นทุนที่ตามมา พร้อมเคสสั้นหนึ่งย่อหน้า"),
        ),
        kit="checklist",
        scenes=_SCENES_PLANT + _SCENES_PEOPLE,
    ),
    "SUSTAINABILITY": Profile(
        sections=(
            ("กฎและขอบเขตที่กระทบลูกค้า",
             "ขอบเขตการรายงานครอบคลุมอะไร และกระทบธุรกิจลูกค้าทางไหน"),
            ("ตัวเลขที่ต้องเก็บ",
             "ข้อมูลที่ต้องเก็บ เก็บจากไหน และแปลงเป็นผลลัพธ์ด้วยวิธีใด"),
        ),
        kit="calculator",
        scenes=_SCENES_PLANT + _SCENES_BUILDING,
    ),
}


def profile_for(pillar: str) -> Profile:
    """Unknown pillar falls back to TECHNICAL, matching ExpertAgent."""
    return FORMAT_PROFILES.get(pillar, FORMAT_PROFILES["TECHNICAL"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_formats.py -q && ruff check .`
Expected: 9 passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/agents/formats.py tests/test_formats.py
git commit -m "feat(formats): per-pillar format profile registry"
```

---

### Task 2: Deterministic scene selection

**Files:**
- Modify: `src/agents/formats.py` (append; keep data above, one pure function below)
- Test: `tests/test_formats.py` (append)

**Interfaces:**
- Consumes: `Profile.scenes` from Task 1.
- Produces: `scene_for(day: date, industry: str, scenes: Sequence[str], recent: Sequence[str] = ()) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_formats.py (append)
from datetime import date

from src.agents.formats import scene_for

POOL = ("โรงพยาบาล 24 ชั่วโมง", "โรงแรมริมทะเล", "อาคารสำนักงานให้เช่า",
        "โรงงานกระดาษ", "CFO กลุ่มค้าปลีก")


def test_same_day_and_industry_always_gives_the_same_scene():
    a = scene_for(date(2026, 10, 1), "Hospitality", POOL)
    b = scene_for(date(2026, 10, 1), "Hospitality", POOL)
    assert a == b


def test_different_industries_can_differ_on_the_same_day():
    seen = {scene_for(date(2026, 10, 1), ind, POOL)
            for ind in ["Hospitality", "Food", "Automotive", "Retail"]}
    assert len(seen) > 1


def test_three_consecutive_days_give_three_different_scenes():
    d1 = scene_for(date(2026, 10, 1), "Food", POOL)
    d2 = scene_for(date(2026, 10, 2), "Food", POOL, recent=[d1])
    d3 = scene_for(date(2026, 10, 3), "Food", POOL, recent=[d2, d1])
    assert len({d1, d2, d3}) == 3


def test_recent_covering_the_whole_pool_still_returns_a_scene():
    # Never raise: a small pool must degrade, not crash the run.
    assert scene_for(date(2026, 10, 4), "Food", POOL, recent=POOL) in POOL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_formats.py -q -k scene`
Expected: FAIL — `ImportError: cannot import name 'scene_for'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agents/formats.py (append at the bottom)
import hashlib
from collections.abc import Sequence
from datetime import date


def scene_for(day: date, industry: str, scenes: Sequence[str],
              recent: Sequence[str] = ()) -> str:
    """Pick a case scene deterministically (spec A2 / v1 §4).

    Same (day, industry, pool) always yields the same scene so the choice
    is testable, and scenes used on recent days are skipped so the reader
    does not meet the same factory manager twice in a row. The model never
    chooses.
    """
    if not scenes:
        raise ValueError("scene pool must not be empty")
    digest = hashlib.sha256(industry.encode("utf-8")).digest()
    start = (day.toordinal() + digest[0]) % len(scenes)
    rotated = list(scenes[start:]) + list(scenes[:start])
    for scene in rotated:
        if scene not in recent:
            return scene
    return rotated[0]  # pool smaller than the recent window
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_formats.py -q && ruff check .`
Expected: 13 passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/agents/formats.py tests/test_formats.py
git commit -m "feat(formats): deterministic no-repeat scene selection"
```

---

### Task 3: Recall candidates from the existing summaries rail

**Files:**
- Modify: `src/utils/index_builder.py` (add one method next to `find_related`, around line 204)
- Test: `tests/test_index_builder_recall.py`

**Interfaces:**
- Consumes: `IndexBuilder.collect_articles()` (returns dicts with `id`, `title`, `date` `YYYY-MM-DD`, `cluster`, `level`), `IndexBuilder._load_summaries()` (`{file_id: {"tldr": str, "html_id": str}}`).
- Produces: `IndexBuilder.recall_candidates(today: date, cluster: str = "", limit: int = 2, min_age_days: int = 3, max_age_days: int = 14) -> list[dict]` — each `{"title": str, "date": str, "tldr": str}`, same-cluster first, newest first, only entries that have a non-empty `tldr`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_index_builder_recall.py
from datetime import date
from unittest.mock import MagicMock, patch

from src.utils.index_builder import IndexBuilder

TODAY = date(2026, 10, 15)
ARTICLES = [
    {"id": "a", "title": "Chiller COP", "date": "2026-10-14", "cluster": "HVAC", "level": 1},
    {"id": "b", "title": "Pump curves", "date": "2026-10-10", "cluster": "Pump", "level": 2},
    {"id": "c", "title": "Cooling tower", "date": "2026-10-08", "cluster": "HVAC", "level": 2},
    {"id": "d", "title": "Ancient post", "date": "2026-08-01", "cluster": "HVAC", "level": 1},
]
SUMMARIES = {
    "a": {"tldr": "COP บอกประสิทธิภาพ chiller"},
    "b": {"tldr": "เลือกปั๊มต้องดูจุดทำงานจริง"},
    "c": {"tldr": "คูลลิ่งทาวเวอร์ทิ้งความร้อน"},
    "d": {"tldr": "ของเก่ามาก"},
}


def _builder():
    b = IndexBuilder(MagicMock(), MagicMock())
    b.collect_articles = MagicMock(return_value=ARTICLES)
    b._load_summaries = MagicMock(return_value=SUMMARIES)
    return b


def test_skips_material_younger_than_three_days():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC")
    assert "Chiller COP" not in [p["title"] for p in picked]


def test_skips_material_older_than_fourteen_days():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC")
    assert "Ancient post" not in [p["title"] for p in picked]


def test_prefers_the_same_cluster_then_fills_from_others():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC", limit=2)
    assert [p["title"] for p in picked] == ["Cooling tower", "Pump curves"]


def test_entries_carry_their_tldr():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC", limit=1)
    assert picked[0]["tldr"] == "คูลลิ่งทาวเวอร์ทิ้งความร้อน"


def test_articles_without_a_tldr_are_not_offered():
    b = _builder()
    b._load_summaries = MagicMock(return_value={"c": {"tldr": ""}})
    assert b.recall_candidates(TODAY, cluster="HVAC") == []


def test_drive_failure_returns_empty_instead_of_raising():
    b = _builder()
    b.collect_articles = MagicMock(side_effect=RuntimeError("drive down"))
    assert b.recall_candidates(TODAY, cluster="HVAC") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_index_builder_recall.py -q`
Expected: FAIL — `AttributeError: 'IndexBuilder' object has no attribute 'recall_candidates'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/utils/index_builder.py — insert directly after find_related()
    def recall_candidates(self, today, cluster: str = "", limit: int = 2,
                          min_age_days: int = 3,
                          max_age_days: int = 14) -> list[dict]:
        """Articles old enough to be worth recalling, young enough to be
        recallable (spec A3). Same cluster first, newest first. Best-effort:
        any Drive or summaries failure returns [] so the daily email still
        goes out (spec C3)."""
        from datetime import date as _date

        try:
            articles = self.collect_articles()
            summaries = self._load_summaries()
        except Exception as e:  # noqa: BLE001 — best-effort by design
            logger.warning(f"recall_candidates unavailable (non-blocking): {e}")
            return []

        picks: list[dict] = []
        for a in articles:
            try:
                published = _date.fromisoformat(a["date"])
            except (KeyError, ValueError):
                continue
            age = (today - published).days
            if not (min_age_days <= age <= max_age_days):
                continue
            tldr = (summaries.get(a["id"], {}) or {}).get("tldr", "").strip()
            if not tldr:
                continue
            picks.append({"title": a["title"], "date": a["date"], "tldr": tldr,
                          "cluster": a.get("cluster", "General")})

        picks.sort(key=lambda p: (p["cluster"] != cluster, p["date"]),
                   reverse=False)
        picks.sort(key=lambda p: (p["cluster"] != cluster, -_ordinal(p["date"])))
        return picks[:limit]
```

and add this module-level helper near the top of `index_builder.py`:

```python
def _ordinal(iso_date: str) -> int:
    from datetime import date as _date
    try:
        return _date.fromisoformat(iso_date).toordinal()
    except ValueError:
        return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_index_builder_recall.py -q && ruff check .`
Expected: 6 passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/utils/index_builder.py tests/test_index_builder_recall.py
git commit -m "feat(index): recall candidates from stored TL;DRs (3-14 days)"
```

---

### Task 4: Translator prompt assembly

**Files:**
- Modify: `src/agents/translator_agent.py` (replace the module-level `PROMPT` at lines 7-93 and `simplify` at 95-112)
- Test: `tests/test_translator_agent.py` (extend the existing file)

**Interfaces:**
- Consumes: `profile_for`, `KIT_SPECS`, `LEVEL_GUIDE`, `scene_for` (Tasks 1-2); recall items from Task 3.
- Produces: `build_prompt(*, topic, pillar, level, industry, expert_content, scene, recall_items) -> str` and `TranslatorAgent.simplify(expert_content, industry_context, topic, pillar, *, level=1, industry="ทั่วไป", scene="", recall_items=()) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_translator_agent.py (append)
from src.agents.formats import FORMAT_PROFILES, KIT_SPECS
from src.agents.translator_agent import build_prompt

ANCHORS = ["## 💡 ประเด็นวันนี้", "Consultant Move",
           "Knowledge Capture", "## 📖 ศัพท์น่ารู้"]


def _prompt(pillar="TECHNICAL", **kw):
    args = dict(topic="Chiller COP", pillar=pillar, level=2,
                industry="Hospitality", expert_content="ข้อเท็จจริงที่ตรวจแล้ว",
                scene="โรงแรมริมทะเล", recall_items=())
    args.update(kw)
    return build_prompt(**args)


@pytest.mark.parametrize("pillar", list(FORMAT_PROFILES))
def test_every_pillar_prompt_keeps_all_four_anchors(pillar):
    p = _prompt(pillar)
    for anchor in ANCHORS:
        assert anchor in p, f"{pillar} lost anchor {anchor}"


@pytest.mark.parametrize("pillar", list(FORMAT_PROFILES))
def test_prompt_carries_that_pillars_sections_and_kit(pillar):
    p = _prompt(pillar)
    for title, _ in FORMAT_PROFILES[pillar].sections:
        assert title in p
    assert KIT_SPECS[FORMAT_PROFILES[pillar].kit].label in p


def test_prompt_states_one_mental_model_and_the_level():
    p = _prompt(level=3)
    assert "หลักคิดวันนี้" in p
    assert "L3" in p


def test_prompt_pins_the_assigned_scene():
    assert "โรงแรมริมทะเล" in _prompt()


def test_recall_block_appears_only_when_items_are_supplied():
    assert "🔁 ทวนของเก่า" not in _prompt()
    with_items = _prompt(recall_items=[
        {"title": "Pump curves", "date": "2026-10-10",
         "tldr": "เลือกปั๊มต้องดูจุดทำงานจริง"}])
    assert "🔁 ทวนของเก่า" in with_items
    assert "🔑 เฉลย" in with_items
    assert "Pump curves" in with_items


def test_length_targets_match_the_amended_spec():
    p = _prompt()
    assert "600" in p and "700" in p


def test_simplify_passes_the_whole_fact_checked_draft():
    tail = "TAIL-FACT-42 kWh"
    g = _CapturingGemini()
    TranslatorAgent(g).simplify(("ข้อเท็จจริง " * 200) + tail, None,
                                "Topic", "TECHNICAL", level=1,
                                industry="Food", scene="โรงงานกระดาษ")
    assert tail in g.prompt
```

Note: `_CapturingGemini` already exists at the top of this test file; `import pytest` must be added if absent.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_translator_agent.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_prompt'`

- [ ] **Step 3: Write minimal implementation**

Replace the whole `PROMPT` constant and `simplify` method with:

```python
# src/agents/translator_agent.py
import logging

from src.agents.formats import KIT_SPECS, LEVEL_GUIDE, profile_for
from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

BASE_RULES = """
กฎ:
- **ห้ามใส่คำทักทาย** เช่น "สวัสดีทีมงาน Sales..." — เริ่มด้วย "## 💡 ประเด็นวันนี้" ตรง ๆ
- **ห้ามใส่ประโยคแนะนำตัวเอง** เช่น "ในฐานะ Senior Engineer", "ผมขอแบ่งปัน"
- **ห้ามใส่ tagline** เกี่ยวกับ "ยกระดับทีม" — Designer ใส่ใน footer แล้ว
- ภาษาไทยเป็นหลัก ทับศัพท์ English ได้
- **ห้ามใช้ LaTeX หรือ $...$** — เขียนหน่วยและสูตรเป็นข้อความธรรมดา เช่น tCO2e, kWh/ปี
- **ใช้ข้อเท็จจริงและตัวเลขจาก "เนื้อหาเทคนิค" ก่อนเสมอ** ถ้าประมาณเองให้ใส่ qualifier
- ห้ามใส่ชื่อบริษัทจริง
- **bullet ใช้ "- " เท่านั้น** ห้ามใช้ "*" หรือ "•" และทุก bullet ต้องอยู่บรรทัดของตัวเอง
- ความยาวเนื้อหาหลัก 600–700 คำ + เครื่องมือ ~150 คำ + ทวนของเก่า ~80 คำ
  ความยาวต้องมาจากสาระ ไม่ใช่คำฟุ่มเฟือย
"""

HEAD_TMPL = """
คุณคือ Consultant Trainer ของ PTT NGR ESP
เขียน Knowledge Sharing email เพื่อพัฒนาทีม Sales และ Technical

หัวข้อ: {topic}
Pillar: {pillar}
ระดับความลึก: {level_guide}
ฉากที่ต้องใช้ในตัวอย่าง/เคส: **{scene}** (ห้ามเปลี่ยนไปใช้ฉากอื่น)
เนื้อหาเทคนิคที่ผ่านการตรวจแล้ว: {expert_content}
บริบทอุตสาหกรรม: {industry}

Output format — Markdown ตรง ๆ ห้ามมีคำนำหน้า:

## 💡 ประเด็นวันนี้

[1 ประโยค ≤25 คำ — ประเด็นเชิงกลยุทธ์ที่เอาไปใช้กับลูกค้าได้ทันที]

**หลักคิดวันนี้:** [≤2 ประโยค — หลักคิดเดียวที่ผู้อ่านต้องจำให้ได้
ทุกหัวข้อด้านล่างต้องรับใช้หลักคิดนี้ ถ้าอะไรไม่เกี่ยวให้ตัดทิ้ง]
"""

SECTION_TMPL = """
## {index}. {title}

[{intent}]
"""

TAIL_TMPL = """
## {cmove_index}. Consultant Move

[1–2 ประโยคพร้อมใช้กับลูกค้าวันนี้]

## 🧰 {kit_label}

{kit_instructions}

## {kc_index}. Knowledge Capture

[1–2 ประโยคสรุปหลักคิดวันนี้ให้จำได้]

**Key formulas / heuristics:**

- [formula หรือ rule of thumb 1]
- [formula หรือ rule of thumb 2]

## 📖 ศัพท์น่ารู้

- [Term1] = [นิยามสั้น]
- [Term2] = [นิยามสั้น]
- [Term3] = [นิยามสั้น]
"""

RECALL_TMPL = """
## 🔁 ทวนของเก่า

[2 คำถามจากบทความเก่าด้านล่าง — ถามให้ตอบจากความจำ ห้ามเฉลยตรงนี้
แต่ละคำถามขึ้นต้นด้วย "- " และลงท้ายด้วย "?"]

บทความเก่าที่ให้ใช้ตั้งคำถาม:
{recall_sources}

## 🔑 เฉลย

[เฉลย 2 ข้อตามลำดับ ข้อละ 1–2 ประโยค ขึ้นต้นด้วย "- "]
"""


def build_prompt(*, topic: str, pillar: str, level: int, industry: str,
                 expert_content: str, scene: str, recall_items=()) -> str:
    profile = profile_for(pillar)
    kit = KIT_SPECS[profile.kit]
    parts = [HEAD_TMPL.format(
        topic=topic, pillar=pillar,
        level_guide=LEVEL_GUIDE.get(int(level or 1), LEVEL_GUIDE[1]),
        scene=scene, expert_content=expert_content[:12000],
        industry=industry or "ทั่วไป")]
    for i, (title, intent) in enumerate(profile.sections, start=1):
        parts.append(SECTION_TMPL.format(index=i, title=title, intent=intent))
    n = len(profile.sections)
    parts.append(TAIL_TMPL.format(cmove_index=n + 1, kc_index=n + 2,
                                  kit_label=kit.label,
                                  kit_instructions=kit.instructions))
    if recall_items:
        sources = "\n".join(
            f'- {it["title"]} ({it["date"]}): {it["tldr"]}' for it in recall_items)
        parts.append(RECALL_TMPL.format(recall_sources=sources))
    parts.append(BASE_RULES)
    return "\n".join(parts)


class TranslatorAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def simplify(self, expert_content: str, industry_context: str,
                 topic: str, pillar: str, *, level: int = 1,
                 industry: str = "ทั่วไป", scene: str = "",
                 recall_items=()) -> str:
        logger.info(f"✍️ Translator: {pillar} · L{level} · ฉาก {scene or '-'}")
        return self.gemini.generate(
            build_prompt(topic=topic, pillar=pillar, level=level,
                         industry=industry, expert_content=expert_content,
                         scene=scene, recall_items=recall_items),
            agent_tag="translator",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_translator_agent.py -q && ruff check .`
Expected: all passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/agents/translator_agent.py tests/test_translator_agent.py
git commit -m "feat(translator): assemble prompt from pillar profile, level, scene, recall"
```

---

### Task 5: Wire the pipeline — scene history, recall, and kit into main

**Files:**
- Modify: `src/main.py:155-182` (translator call site; `IndexBuilder` is constructed at line 182 — move it above the translator call)
- Test: `tests/test_main_format_wiring.py`

**Interfaces:**
- Consumes: `profile_for`, `scene_for`, `IndexBuilder.recall_candidates`, `TranslatorAgent.simplify(...)` keyword arguments.
- Produces: no new public API; `EditorAgent.review` gains `kit=` and `scene=` (Task 6) and is called with them here.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main_format_wiring.py
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src import main as main_mod

BKK = ZoneInfo("Asia/Bangkok")
CALENDAR = (
    "- **2026-05-04**: TECHNICAL | Chiller 101 | Hospitality | chiller "
    "| cluster=HVAC | level=3\n"
)


@pytest.fixture
def deps():
    drive, gemini = MagicMock(), MagicMock()
    patches = [
        patch.object(main_mod, "DriveAPI", return_value=drive),
        patch.object(main_mod, "GeminiClient", return_value=gemini),
        patch.object(main_mod, "ResearchCache"),
        patch.object(main_mod, "validate_startup"),
        patch.object(main_mod, "ResearchAgent"),
        patch.object(main_mod, "ExpertAgent"),
        patch.object(main_mod, "IndustryAgent"),
        patch.object(main_mod, "FactCheckerAgent"),
        patch.object(main_mod, "TranslatorAgent"),
        patch.object(main_mod, "EditorAgent"),
        patch.object(main_mod, "DesignerAgent"),
        patch.object(main_mod, "ImageAgent"),
        patch.object(main_mod, "IndexBuilder"),
        patch.object(main_mod, "CalendarPlannerAgent"),
        patch.object(main_mod, "send_daily_email", return_value=True),
        patch.object(main_mod, "markdown_to_docx_bytes", return_value=b"d"),
    ]
    for p in patches:
        p.start()
    drive.download_file.return_value = CALENDAR
    yield drive
    for p in patches:
        p.stop()


def _run():
    with patch.object(main_mod, "now_bangkok",
                      return_value=datetime(2026, 5, 4, 8, 0, tzinfo=BKK)):
        return main_mod.main(skip_validation=True, dry_run=True)


def test_translator_receives_level_industry_and_a_scene(deps):
    _run()
    kwargs = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs
    assert kwargs["level"] == 3
    assert kwargs["industry"] == "Hospitality"
    assert kwargs["scene"], "a scene must always be assigned"


def test_recall_items_come_from_the_index(deps):
    main_mod.IndexBuilder.return_value.recall_candidates.return_value = [
        {"title": "Pump curves", "date": "2026-04-28", "tldr": "x"}]
    _run()
    kwargs = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs
    assert kwargs["recall_items"][0]["title"] == "Pump curves"


def test_recall_failure_does_not_stop_the_run(deps):
    main_mod.IndexBuilder.return_value.recall_candidates.side_effect = \
        RuntimeError("drive down")
    result = _run()
    assert result["status"] == "success"
    kwargs = main_mod.TranslatorAgent.return_value.simplify.call_args.kwargs
    assert kwargs["recall_items"] == []


def test_editor_is_told_which_kit_and_scene_to_enforce(deps):
    _run()
    kwargs = main_mod.EditorAgent.return_value.review.call_args.kwargs
    assert kwargs["kit"] == "checklist"   # TECHNICAL profile
    assert kwargs["scene"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_format_wiring.py -q`
Expected: FAIL — `KeyError: 'level'` (simplify is still called positionally)

- [ ] **Step 3: Write minimal implementation**

In `src/main.py`, add the import next to the other agent imports:

```python
from src.agents.formats import profile_for, scene_for
```

Then replace the translator/editor block:

```python
    index = IndexBuilder(drive, s)
    profile = profile_for(topic["pillar"])
    scene = scene_for(topic["date"].date(), topic.get("industry", "ทั่วไป"),
                      profile.scenes, recent=_recent_scenes(index, topic))
    try:
        recall_items = index.recall_candidates(
            topic["date"].date(), cluster=topic.get("cluster", "General"))
    except Exception as e:  # noqa: BLE001 — recall is best-effort (spec C3)
        logger.warning(f"recall block skipped (non-blocking): {e}")
        recall_items = []

    translated = require_ok("translator", TranslatorAgent(gemini).simplify(
        verified, None, topic["topic"], topic["pillar"],
        level=int(topic.get("level", 1) or 1),
        industry=topic.get("industry", "ทั่วไป"),
        scene=scene, recall_items=recall_items))

    edited = EditorAgent(gemini).review(translated, kit=profile.kit, scene=scene)
```

and delete the later `index = IndexBuilder(drive, s)` line so it is constructed once. Add the helper near the other module-level functions in `main.py`:

```python
def _recent_scenes(index, topic) -> list[str]:
    """Scenes used on the last two publication days, so today differs.

    Best-effort: scene history lives in the summaries index; if it is not
    available, an empty list simply means 'no constraint'.
    """
    try:
        return [e["scene"] for e in index.recent_scenes(limit=2) if e.get("scene")]
    except Exception:  # noqa: BLE001
        return []
```

Add the matching storage to `IndexBuilder` (next to `update_summary`):

```python
    def recent_scenes(self, limit: int = 2) -> list[dict]:
        """Most recent stored scenes, newest first (spec §4 no-repeat rule)."""
        summaries = self._load_summaries()
        rows = [v for v in summaries.values() if isinstance(v, dict) and v.get("scene")]
        rows.sort(key=lambda r: r.get("date", ""), reverse=True)
        return rows[:limit]
```

and extend the existing `update_summary(...)` call in `main.py:260` to persist today's scene:

```python
                index.update_summary(docx_id, tldr, html_id, scene=scene,
                                     date=date_str)
```

with `update_summary` gaining `scene: str = ""` and `date: str = ""` keyword parameters that are stored in the same record.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -q && ruff check .`
Expected: all passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/main.py src/utils/index_builder.py tests/test_main_format_wiring.py
git commit -m "feat(pipeline): pass level, scene and recall items through the daily run"
```

---

### Task 6: Editor gates for the new shape

**Files:**
- Modify: `src/agents/editor_agent.py` (`check` at 106-126, `review` at 96-104, `PROMPT` at 36-54)
- Test: `tests/test_editor_agent.py` (extend)

**Interfaces:**
- Consumes: `kit` and `scene` from Task 5.
- Produces: `EditorAgent.check(md, kit: str = "", scene: str = "") -> list[str]`, `EditorAgent.review(md, *, kit: str = "", scene: str = "") -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_editor_agent.py (append)
CHECKLIST_OK = """## 💡 ประเด็นวันนี้
x

## 🧰 Checklist เดินหน้างาน

- ☐ วัดอุณหภูมิน้ำเย็นออก ควรอยู่ 7 °C ถ้าสูงกว่าแปลว่าโหลดเกิน
- ☐ วัด Excess air ควร 15-20% ถ้าเกินแปลว่าสูญเสียความร้อน
- ☐ อ่านค่าความดันตกคร่อม filter ควร < 250 Pa ถ้าเกินต้องล้าง
- ☐ ตรวจ schedule เครื่องทำงานนอกเวลาหรือไม่
- ☐ ตรวจฉนวนท่อมีจุดชำรุดหรือไม่
- ☐ ตรวจ log การบำรุงรักษาย้อนหลัง 12 เดือน

## 3. Consultant Move
ถาม

## 4. Knowledge Capture
สรุป

## 📖 ศัพท์น่ารู้
- COP = ประสิทธิภาพ
"""


def test_checklist_kit_passes_its_gate():
    assert EditorAgent.check(CHECKLIST_OK, kit="checklist") == []


def test_checklist_with_square_brackets_is_rejected():
    md = CHECKLIST_OK.replace("- ☐ ", "- [ ] ")
    assert any("☐" in i for i in EditorAgent.check(md, kit="checklist"))


def test_checklist_needs_at_least_six_items():
    md = CHECKLIST_OK.replace(
        "- ☐ ตรวจ log การบำรุงรักษาย้อนหลัง 12 เดือน\n", "")
    assert any("6" in i for i in EditorAgent.check(md, kit="checklist"))


def test_missing_kit_section_is_flagged():
    md = CHECKLIST_OK.replace("## 🧰 Checklist เดินหน้างาน", "## 4. Takeaways")
    assert any("🧰" in i for i in EditorAgent.check(md, kit="checklist"))


def test_questions_kit_needs_questions_and_objections():
    md = CHECKLIST_OK.replace("## 🧰 Checklist เดินหน้างาน",
                              "## 🧰 ชุดคำถามเจาะลูกค้า")
    issues = EditorAgent.check(md, kit="questions")
    assert any("คำถาม" in i for i in issues)


def test_calculator_reference_numbers_need_a_source():
    md = CHECKLIST_OK.replace(
        "## 🧰 Checklist เดินหน้างาน",
        "## 🧰 สูตรคำนวณพร้อมใช้\n\nประหยัด = kWh × 4.2 บาท/kWh\n"
        "ตัวอย่าง: 1000 kWh × 4.2 บาท/kWh = 4200 บาท/ปี")
    assert any("ที่มา" in i for i in EditorAgent.check(md, kit="calculator"))


def test_assigned_scene_must_appear():
    issues = EditorAgent.check(CHECKLIST_OK, kit="checklist", scene="โรงแรมริมทะเล")
    assert any("ฉาก" in i for i in issues)


def test_recall_block_requires_its_answer_box():
    md = CHECKLIST_OK + "\n## 🔁 ทวนของเก่า\n- คำถาม?\n"
    assert any("เฉลย" in i for i in EditorAgent.check(md, kit="checklist"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_editor_agent.py -q -k "kit or scene or recall or checklist"`
Expected: FAIL — `TypeError: check() got an unexpected keyword argument 'kit'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agents/editor_agent.py — add near the other regexes
KIT_HEADING_RE = re.compile(r"^##\s*🧰\s*\S", re.MULTILINE)
CHECKBOX_RE = re.compile(r"^- ☐ ", re.MULTILINE)
SQUARE_BOX_RE = re.compile(r"^- \[ ?\]", re.MULTILINE)
QUESTION_RE = re.compile(r"^-?\s*.+\?\s*$", re.MULTILINE)
OBJECTION_RE = re.compile(r"\*\*ลูกค้า:\*\*")
FORMULA_RE = re.compile(r"^[^#\n]*=[^\n]*$", re.MULTILINE)
SOURCE_TAG_RE = re.compile(r"—\s*ที่มา\s*:")
RECALL_RE = re.compile(r"^##\s*🔁", re.MULTILINE)
ANSWER_RE = re.compile(r"^##\s*🔑", re.MULTILINE)
ANCHOR_PATTERNS = {
    "💡 ประเด็นวันนี้": re.compile(r"^##\s*💡\s*ประเด็นวันนี้", re.MULTILINE),
    "Consultant Move": re.compile(r"Consultant Move"),
    "Knowledge Capture": re.compile(r"Knowledge Capture"),
    "📖 ศัพท์น่ารู้": re.compile(r"📖\s*ศัพท์น่ารู้"),
}
```

Replace `check` and `review` with:

```python
    @staticmethod
    def check(md: str, kit: str = "", scene: str = "") -> list[str]:
        issues = []
        for name, pattern in ANCHOR_PATTERNS.items():
            if not pattern.search(md):
                issues.append(f"ขาด anchor '{name}' — designer/recap จะพัง")

        nums = NUMBER_WITH_UNIT_RE.findall(md)
        if len(nums) < 3:
            issues.append(
                f"มีตัวเลขจริง+หน่วย {len(nums)} จุด ต้องการอย่างน้อย 3")
        if len(md.split()) > 1200:
            issues.append(f"เนื้อหายาว {len(md.split())} คำ ต้องการไม่เกิน 1,000")
        if SPECIFIC_COMPANY_RE.search(md):
            issues.append("พบชื่อบริษัทเฉพาะ — เปลี่ยนเป็น 'โรงงานขนาด X แห่งหนึ่ง'")

        if kit:
            if not KIT_HEADING_RE.search(md):
                issues.append("ขาดหัวข้อเครื่องมือ '## 🧰 ...'")
            issues += EditorAgent._kit_issues(md, kit)
        if scene and scene not in md:
            issues.append(f"ไม่ได้ใช้ฉากที่กำหนด — ต้องอ้างถึง '{scene}'")
        if RECALL_RE.search(md) and not ANSWER_RE.search(md):
            issues.append("มี '🔁 ทวนของเก่า' แต่ขาดกล่องเฉลย '## 🔑 เฉลย'")
        return issues

    @staticmethod
    def _kit_issues(md: str, kit: str) -> list[str]:
        issues: list[str] = []
        if kit == "checklist":
            if SQUARE_BOX_RE.search(md):
                issues.append("checklist ใช้ '- [ ]' — ต้องใช้ '- ☐ ' เท่านั้น")
            boxes = CHECKBOX_RE.findall(md)
            if len(boxes) < 6:
                issues.append(f"checklist มี {len(boxes)} ข้อ ต้องการอย่างน้อย 6")
            with_numbers = [ln for ln in md.splitlines()
                            if ln.startswith("- ☐ ") and NUMBER_WITH_UNIT_RE.search(ln)]
            if len(with_numbers) < 3:
                issues.append("checklist ต้องมีข้อที่ระบุค่าปกติเป็นตัวเลข+หน่วย ≥3 ข้อ")
        elif kit == "questions":
            questions = [ln for ln in md.splitlines() if ln.strip().endswith("?")]
            if len(questions) < 4:
                issues.append(f"ชุดคำถามมี {len(questions)} ข้อ ต้องการอย่างน้อย 4")
            if len(OBJECTION_RE.findall(md)) < 2:
                issues.append("ต้องมี objection พร้อมคำตอบอย่างน้อย 2 ชุด (**ลูกค้า:**)")
        elif kit == "calculator":
            if not FORMULA_RE.search(md):
                issues.append("สูตรคำนวณต้องมีบรรทัดที่มีเครื่องหมาย '='")
            if not SOURCE_TAG_RE.search(md):
                issues.append("ตัวเลขอ้างอิงต้องมี '— ที่มา: ...' กำกับ")
        return issues

    def review(self, md: str, *, kit: str = "", scene: str = "") -> str:
        md = self.strip_latex(md)
        issues = self.check(md, kit=kit, scene=scene)
        if not issues:
            logger.info("✓ Editor: content passes all checks (no LLM call)")
            return md

        logger.warning(f"✏️  Editor: repairing {len(issues)} issue(s): {issues}")
        bullet_issues = "\n".join(f"- {i}" for i in issues)
        improved = self.gemini.generate(
            PROMPT.format(issues=bullet_issues, content=md),
            agent_tag="editor",
        )
        if improved and not improved.startswith("[Error"):
            return self.strip_latex(improved)
        logger.warning("Editor regen failed — keeping original")
        return md
```

Also update the editor `PROMPT` line `- ความยาวรวมไม่เกิน 1,000 คำ` to
`- ความยาวรวมไม่เกิน 1,000 คำ และห้ามลบหัวข้อ 🧰 / 🔁 / 🔑 ที่มีอยู่`, and drop the now-unused `CASE_STUDY_RE`/`TAKEAWAY_RE`/`GLOSSARY_RE` constants together with the tests that assert on them (`test_check_flags_missing_case_study`, `test_check_flags_missing_takeaways` — replaced by the anchor test above).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -q && ruff check .`
Expected: all passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/agents/editor_agent.py tests/test_editor_agent.py
git commit -m "feat(editor): gate kit, scene, anchors and the recall answer box"
```

---

### Task 7: Render the kit, recall and answer boxes

**Files:**
- Modify: `src/agents/designer_agent.py` (regex block 41-70, CSS at 139-165, `_md_to_html` at 234-250)
- Test: `tests/test_designer_agent.py` (extend)

**Interfaces:**
- Consumes: markdown produced in Tasks 4-6.
- Produces: HTML containing `<div class="kit">`, `<div class="recall">`, `<div class="answers">`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_designer_agent.py (append)
MD_WITH_BOXES = """## 💡 ประเด็นวันนี้
สรุป

## 🧰 Checklist เดินหน้างาน

- ☐ วัดอุณหภูมิน้ำเย็นออก ควรอยู่ 7 °C

## 🔁 ทวนของเก่า

- เมื่อวาน COP ต่ำแปลว่าอะไร?

## 🔑 เฉลย

- แปลว่าเครื่องกินไฟเกินต่อความเย็นที่ได้
"""


def test_kit_section_becomes_its_own_box():
    html = DesignerAgent._md_to_html(MD_WITH_BOXES)
    assert 'class="kit"' in html
    assert "Checklist เดินหน้างาน" in html


def test_recall_and_answers_become_separate_boxes():
    html = DesignerAgent._md_to_html(MD_WITH_BOXES)
    assert 'class="recall"' in html
    assert 'class="answers"' in html
    assert html.index('class="recall"') < html.index('class="answers"'), \
        "answers must come after the questions"


def test_checkbox_character_survives_rendering():
    assert "☐" in DesignerAgent._md_to_html(MD_WITH_BOXES)


def test_boxes_survive_premailer_inlining():
    html = DesignerAgent.create_email(
        MD_WITH_BOXES,
        {"topic": "T", "pillar": "TECHNICAL", "date": datetime(2026, 10, 1)})
    assert "☐" in html
    assert "เฉลย" in html
    assert "<details" not in html, "spec A9 — no <details>, it is unreliable in Gmail"
```

`datetime` and `DesignerAgent` are already imported at the top of this test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_designer_agent.py -q -k "box or checkbox or premailer"`
Expected: FAIL — `assert 'class="kit"' in html`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agents/designer_agent.py — next to CMOVE_RE / KCAPTURE_RE
KIT_RE = re.compile(r'<h2>🧰\s*(.*?)</h2>(.*?)(?=<h2|$)', re.DOTALL)
RECALL_RE = re.compile(r'<h2>🔁\s*(.*?)</h2>(.*?)(?=<h2|$)', re.DOTALL)
ANSWERS_RE = re.compile(r'<h2>🔑\s*(.*?)</h2>(.*?)(?=<h2|$)', re.DOTALL)
```

In `_md_to_html`, after the existing `KCAPTURE_RE` substitution:

```python
        html = KIT_RE.sub(
            r'<div class="kit"><h3>🧰 \1</h3>\2</div>', html)
        html = RECALL_RE.sub(
            r'<div class="recall"><h3>🔁 \1</h3>\2</div>', html)
        html = ANSWERS_RE.sub(
            r'<div class="answers"><h3>🔑 \1</h3>\2</div>', html)
```

In the CSS block next to `.cmove` / `.kcapture` (both email templates):

```css
.bd .kit{{background:#F1F8E9;border:1px solid #C5E1A5;border-radius:8px;padding:14px 18px;margin:18px 0}}
.bd .kit h3{{margin:0 0 8px;font-size:18px;color:#33691E}}
.bd .recall{{background:#FFF8E1;border:1px solid #FFE082;border-radius:8px;padding:14px 18px;margin:18px 0}}
.bd .recall h3{{margin:0 0 8px;font-size:18px;color:#F57F17}}
.bd .answers{{background:#FAFAFA;border:1px dashed #BDBDBD;border-radius:8px;padding:12px 18px;margin:18px 0;color:#555;font-size:16px}}
.bd .answers h3{{margin:0 0 6px;font-size:16px;color:#757575}}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -q && ruff check .`
Expected: all passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/agents/designer_agent.py tests/test_designer_agent.py
git commit -m "feat(designer): render kit, recall and answer boxes"
```

---

### Task 8: Thai reference figures with provenance (A7)

**Files:**
- Create: `docs/references/th-energy-reference.md`
- Modify: `src/agents/formats.py` (calculator `KitSpec.instructions` quotes the table), `src/agents/translator_agent.py` (`build_prompt` injects it for calculator pillars)
- Test: `tests/test_formats.py` (append), `tests/test_translator_agent.py` (append)

**Interfaces:**
- Consumes: `KIT_SPECS["calculator"]`.
- Produces: `REFERENCE_FIGURES: str` in `formats.py` — the literal block quoted into calculator prompts.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_formats.py (append)
from src.agents.formats import REFERENCE_FIGURES


def test_reference_figures_carry_sources():
    lines = [ln for ln in REFERENCE_FIGURES.splitlines() if ln.strip().startswith("-")]
    assert len(lines) >= 4
    assert all("ที่มา" in ln for ln in lines), "every figure needs provenance (A7)"


# tests/test_translator_agent.py (append)
def test_calculator_pillars_receive_the_reference_table():
    assert "ที่มา" in _prompt("SUSTAINABILITY")


def test_non_calculator_pillars_do_not_carry_it():
    assert "ค่าไฟเฉลี่ยภาคอุตสาหกรรม" not in _prompt("SOFTSKILL")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_formats.py tests/test_translator_agent.py -q -k reference`
Expected: FAIL — `ImportError: cannot import name 'REFERENCE_FIGURES'`

- [ ] **Step 3: Write minimal implementation**

Create `docs/references/th-energy-reference.md`:

```markdown
# ตัวเลขอ้างอิงไทย — สำหรับเครื่องมือคำนวณในอีเมลรายวัน

ทุกตัวเลขต้องมีที่มา ถ้าไม่มีที่มา ห้ามใช้. ทบทวนทุกไตรมาส (ผู้ดูแล: Tanet).

- ค่าไฟเฉลี่ยภาคอุตสาหกรรม 4.2 บาท/kWh — ที่มา: PEA/MEA tariff 2569
- Emission factor ไฟฟ้า grid ไทย 0.4999 tCO2e/MWh — ที่มา: TGO CFO 2568
- Emission factor ก๊าซธรรมชาติ 56.1 tCO2e/TJ — ที่มา: IPCC 2006 Vol.2
- ค่าความร้อนก๊าซธรรมชาติ 39 MJ/m3 — ที่มา: PTT NGR spec sheet 2568
- อายุใช้งานหม้อไอน้ำอุตสาหกรรม 15–20 ปี — ที่มา: ASHRAE Equipment Life

> เปลี่ยนตัวเลขที่นี่ที่เดียว แล้ว prompt จะหยิบไปใช้เองในรอบถัดไป
```

In `formats.py`:

```python
REFERENCE_FIGURES = """
ตัวเลขอ้างอิงไทยที่อนุญาตให้ใช้ (ห้ามกุตัวเลขอื่นแล้วอ้างว่าเป็นมาตรฐาน):
- ค่าไฟเฉลี่ยภาคอุตสาหกรรม 4.2 บาท/kWh — ที่มา: PEA/MEA tariff 2569
- Emission factor ไฟฟ้า grid ไทย 0.4999 tCO2e/MWh — ที่มา: TGO CFO 2568
- Emission factor ก๊าซธรรมชาติ 56.1 tCO2e/TJ — ที่มา: IPCC 2006 Vol.2
- ค่าความร้อนก๊าซธรรมชาติ 39 MJ/m3 — ที่มา: PTT NGR spec sheet 2568
- อายุใช้งานหม้อไอน้ำอุตสาหกรรม 15–20 ปี — ที่มา: ASHRAE Equipment Life
ถ้าต้องใช้ตัวเลขนอกรายการนี้ ให้เขียนว่า "ประมาณการ" และห้ามอ้างมาตรฐานใด ๆ
"""
```

In `build_prompt`, after the kit section is appended:

```python
    if profile.kit == "calculator":
        parts.append(REFERENCE_FIGURES)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -q && ruff check .`
Expected: all passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add docs/references/th-energy-reference.md src/agents/formats.py src/agents/translator_agent.py tests/
git commit -m "feat(formats): sourced Thai reference figures for calculator kits"
```

---

### Task 9: Saturday recap becomes retrieval (A4)

**Files:**
- Modify: `src/agents/recap_agent.py` (`PROMPT` at 85-110)
- Test: `tests/test_recap_agent.py` (extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: unchanged public API; the generated markdown now contains `## 🔁 ทวนสัปดาห์นี้` (5 questions), `## 🔑 เฉลย`, and keeps `### 📚 Knowledge Capture`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recap_agent.py (append)
def test_recap_prompt_asks_for_retrieval_not_a_summary():
    drive = _make_drive_with_week({"2026-05-11": "<p>x</p>"})
    gemini = MagicMock()
    gemini.generate.return_value = "## stub"
    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>r</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=True):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False)
    prompt = gemini.generate.call_args.args[0]
    assert "🔁" in prompt and "🔑 เฉลย" in prompt
    assert "5 คำถาม" in prompt
    assert "Knowledge Capture" in prompt, "anchor must survive (renderer + site)"
    assert "ตอบกลับ" not in prompt, "A4/C2 — the mail is one-way, it asks for nothing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recap_agent.py -q -k retrieval`
Expected: FAIL — `assert '🔁' in prompt`

- [ ] **Step 3: Write minimal implementation**

Replace the four-section instruction block in `recap_agent.py` with:

```python
จงเขียน Markdown ภาษาไทย ไม่เกิน 500 คำ ตามโครงนี้:

## สรุปสัปดาห์ที่ {week}

## 🔁 ทวนสัปดาห์นี้

[5 คำถามจากเนื้อหาสัปดาห์นี้ — ถามให้ตอบจากความจำ ห้ามเฉลยตรงนี้
แต่ละข้อขึ้นต้นด้วย "- " ลงท้ายด้วย "?" และอ้างวันสั้น ๆ เช่น (จ.)]

### 📚 Knowledge Capture

[3–5 bullets — ศัพท์ ตัวเลข หรือ framework ที่ควรจำจากสัปดาห์นี้]

## 🔑 เฉลย

[เฉลย 5 ข้อตามลำดับ ข้อละ 1–2 ประโยค ขึ้นต้นด้วย "- "]

ห้ามขอให้ผู้อ่านตอบกลับอีเมล ห้ามขอให้กรอกฟอร์ม — อีเมลนี้เป็นทางเดียว
ผู้อ่านลองตอบในใจแล้วเลื่อนลงมาดูเฉลยเองได้เลย
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -q && ruff check .`
Expected: all passed, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/agents/recap_agent.py tests/test_recap_agent.py
git commit -m "feat(recap): Saturday mail asks five questions instead of summarising"
```

---

### Task 10: Six-pillar dry run and owner review

**Files:**
- Create: `tools/preview_formats.py`
- Modify: `docs/ops-log.md` (baseline row)

**Interfaces:**
- Consumes: the whole pipeline.
- Produces: one HTML file per pillar under the scratch directory plus a printed comparison table.

- [ ] **Step 1: Write the preview tool**

```python
# tools/preview_formats.py
"""Dry-run one article per pillar and report the shape of each result.

Usage: python tools/preview_formats.py <output_dir>
Sends nothing, uploads nothing — it calls main() with dry_run=True and
captures the rendered HTML that would have been emailed.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")

import src.main as m  # noqa: E402

PILLARS = ["TECHNICAL", "INDUSTRY", "FRAMEWORK",
           "SOFTSKILL", "COMPLIANCE", "SUSTAINABILITY"]


def main(outdir: str) -> int:
    Path(outdir).mkdir(parents=True, exist_ok=True)
    original = m.DesignerAgent.create_email
    captured: dict[str, str] = {}

    def capture(content, metadata, *a, **kw):
        html = original(content, metadata, *a, **kw)
        if "image_bytes" in kw:
            captured[metadata["pillar"]] = html
        return html

    m.DesignerAgent.create_email = staticmethod(capture)
    for pillar in PILLARS:
        print(f"--- {pillar}")
        m.main(dry_run=True, skip_validation=True)

    print(f"\n{'pillar':16s} {'words':>6s} {'kit':>4s} {'recall':>7s} {'☐':>3s}")
    for pillar, html in captured.items():
        text = re.sub(r"<[^>]+>", " ", html)
        Path(outdir, f"{pillar}.html").write_text(html, encoding="utf-8")
        print(f"{pillar:16s} {len(text.split()):6d} "
              f"{'yes' if 'class=\"kit\"' in html else 'NO':>4s} "
              f"{'yes' if 'class=\"recall\"' in html else 'no':>7s} "
              f"{text.count('☐'):3d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
```

- [ ] **Step 2: Run it against the real pipeline**

Run: `python tools/preview_formats.py <scratch>/formats`
Expected: six files written; every row shows `kit=yes`; word counts land between 700 and 1,100; checklist pillars show `☐ ≥ 6`.

- [ ] **Step 3: Send two samples to the owner for review**

Email the two most different pillars (e.g. SOFTSKILL and SUSTAINABILITY) to `tanet.i@pttplc.com` only, using the same one-recipient script used on 2026-09-11 (SMTP 465 locally; port 587 is blocked on the corporate network).

- [ ] **Step 4: Add the one-line run summary and record the limit (A8)**

In `src/main.py`, next to the existing `💰 Daily cost` line:

```python
    logger.info(f"📐 shape={topic['pillar']} kit={profile.kit} "
                f"recall={len(recall_items)} repairs={editor_repairs}")
```

where `editor_repairs` is `1` when `EditorAgent.review` fired its repair
call and `0` otherwise — return it via `EditorAgent.last_repair_count`
(an attribute set inside `review`, defaulting to `0`).

Add one row to `docs/ops-log.md`:

```markdown
| 2026-09-29 | Retention is NOT measured — mail is one-way by owner decision (no replies, no pixels, static site stores nothing). A per-run log line (shape/kit/recall/repairs) exists for operations only. | Measurement | A8/C2 — record the limit instead of inventing a proxy | n/a |
```

- [ ] **Step 5: Commit**

```bash
git add tools/preview_formats.py docs/ops-log.md
git commit -m "chore(preview): six-pillar dry-run tool + measurement baseline"
```

---

### Task 11: Ship it

**Files:**
- Modify: `docs/ops-log.md`

- [ ] **Step 1: Open the PR**

```bash
gh pr create --base main --head chuan \
  --title "Per-pillar email formats + retention loop (spec A1-A9)" \
  --body "Implements docs/superpowers/specs/2026-09-29-email-format-profiles-design.md v2."
```

- [ ] **Step 2: Wait for CI**

Run: `gh pr checks <n>`
Expected: `lint pass`, `pytest pass`.

- [ ] **Step 3: Merge after owner approval of the samples from Task 10**

```bash
gh pr merge <n> --merge
```

- [ ] **Step 4: Verify the first real run**

Check the next morning's run log for: every call `200 OK`, no `[Error`, `class="kit"` present in the archived HTML, and the email delivered to 17 recipients.

- [ ] **Step 5: Watch the run line for one week, then stop watching**

For the first seven runs, read the `📐` line in each run log. The only
thing being looked for is `repairs=1` on the same pillar every day,
which means that pillar's gate is unsatisfiable and is burning an LLM
call daily — fix the gate, do not relax it blindly. After that week no
routine logging is required: retention is not measured, and content
quality is judged by reading the email, not by a number.

---

## Self-review

**Spec coverage:** A1 → Tasks 4+9 (recall + retrieval). A2 → Tasks 1, 4 (mental model, two sections). A3 → Tasks 3, 4, 5, 7. A4 → Task 9, including the one-way rule asserted by test. A5 → Tasks 4, 6 (targets and gate). A6 → Tasks 1, 4, 5 (`LEVEL_GUIDE`, level plumbing). A7 → Tasks 6, 8. A8 (revised: delivery-only logging, retention explicitly unmeasured) → Tasks 10 step 4, 11 step 5. A9 → Task 7 (`no <details>` asserted). v1 §1-§5 → Tasks 1-7. Rollout → Tasks 10-11. No spec section is unimplemented.

**Placeholder scan:** no TBD/TODO; every code step carries real code; every test step carries real assertions.

**Type consistency:** `profile_for` returns `Profile` (Task 1) and is called in Tasks 4-5; `scene_for(day, industry, scenes, recent)` keeps its signature in Tasks 2 and 5; `recall_candidates(today, cluster, limit, …)` returns `list[dict]` with `title`/`date`/`tldr` consumed identically in Tasks 3-5; `EditorAgent.check(md, kit, scene)` and `review(md, *, kit, scene)` match their call site in Task 5.
