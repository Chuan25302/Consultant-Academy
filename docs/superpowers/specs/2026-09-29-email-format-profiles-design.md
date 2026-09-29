# Per-Pillar Email Format Profiles — Design

**Date:** 2026-09-29
**Branch:** `chuan`
**Status:** Approved — ready for implementation plan

## Problem

The daily email reads the same every day. Measured on the eight most
recent published articles (2026-09-18, 21, 22, 23, 24, 25, 28, 29,
pulled from the public KM site):

| Checked | Result |
|---|---|
| Topics | Varied — 94 articles, 6 pillars, no repeats |
| Wording | Varied — no sentence ≥25 chars repeats across articles (only site chrome does) |
| **Section skeleton** | **Identical in 8/8** — same six headings, same order |
| **Narrative beats** | **Situation → Complication → Approach → Result in 8/8** |
| **Case-study character** | `ผู้จัดการโรงงานบอกเราว่า` in **7/8** — the same factory manager, every day |
| Reading time | ~11 minutes, every issue |

The cause is in the code, not the model. `ExpertAgent` already branches
per pillar (`src/agents/expert_agent.py:308` — `PROMPTS` holds six
pillar-specific templates producing six different section structures).
`TranslatorAgent` then flattens all of them through one hard-coded
template (`src/agents/translator_agent.py:7-93`), so whatever variety
the expert stage produced is discarded before the reader sees it.

A second, related complaint: the closing `Takeaways` section gives
advice the reader nods at but cannot act on ("ชูประเด็นความเสี่ยงจาก
กฎหมายเป็นตัวเปิดบทสนทนา").

## Goals

- Each pillar produces a **visibly different article shape**, so the
  reader cannot predict the layout by day three.
- Every issue ships **one artifact the team can use the same day**: a
  site checklist, a customer question set with objection handling, or a
  ready-to-fill calculation.
- Case scenes vary (hospital, hotel, contractor, procurement, CFO…)
  instead of one recurring factory manager.
- No increase in LLM calls or daily cost.

## Non-Goals

- Changing topic selection or the calendar (topics are already varied).
- Changing `ExpertAgent`, `FactCheckerAgent`, or the research stage.
- Changing the Saturday recap (it reads the `Knowledge Capture` anchor,
  which this design preserves).
- Making the email shorter — length target stays 800–1,000 words.

## Constraints discovered in the code

Four headings are parsed by other components. Renaming or dropping any
of them silently breaks rendering:

| Anchor | Consumer |
|---|---|
| `## 💡 ประเด็นวันนี้` | `designer_agent.py:65-70` — TL;DR block + site summary line |
| `Consultant Move` | `designer_agent.py:41-44` — callout box |
| `Knowledge Capture` | `designer_agent.py:49-51` — callout box; `recap_agent.py` weekly extraction |
| `## 📖 ศัพท์น่ารู้` | `designer_agent.py:58-60` — glossary box |

Therefore the design is **fixed frame, variable middle**.

Checkbox markdown is not available: the project renders with
python-markdown + `sane_lists,extra,nl2br` (`designer_agent.py:235`),
which leaves `- [ ]` as the literal text `[ ]` in both email and site,
and `docx_writer.py:103` turns it into a bullet carrying `[ ]`.
Checklist items therefore use the character `☐` (`- ☐ …`), which needs
no code change and renders correctly in email, site, and .docx.

## Design

### 1. Format profile registry — `src/agents/formats.py` (new)

One profile per pillar, mirroring the existing `ExpertAgent.PROMPTS`
convention:

```python
FORMAT_PROFILES = {
    "TECHNICAL": Profile(
        sections=[("หน้างานบอกอะไร", "อาการ/ค่าที่วัดได้ + วิธีอ่านค่า"),
                  ("เคสสั้น: จากอาการสู่ทางแก้", "…")],
        kit="checklist",
        scenes=[...],
    ),
    ...
}
```

Middle sections and kit per pillar:

| Pillar | Section 1 | Section 2 | Kit |
|---|---|---|---|
| TECHNICAL | หน้างานบอกอะไร | เคสสั้น: จากอาการสู่ทางแก้ | checklist |
| INDUSTRY | โปรไฟล์ธุรกิจ + Energy Profile | 3 จุดปวดที่ขายได้ + สัญญาณสังเกต | questions |
| FRAMEWORK | โจทย์ที่กรอบนี้แก้ | ลองใช้กับเคสจริงทีละขั้น | calculator |
| SOFTSKILL | บทสนทนาจริง (4–6 บรรทัด) | ถอดบทเรียน: ทำไมประโยคนั้นได้ผล | questions |
| COMPLIANCE | ข้อกำหนดที่ต้องรู้ | ถ้าไม่ทำเกิดอะไร — บทลงโทษ/ต้นทุน | checklist |
| SUSTAINABILITY | กฎและขอบเขตที่กระทบลูกค้า | ตัวเลขที่ต้องเก็บ + วิธีคำนวณ | calculator |

An unknown pillar falls back to the TECHNICAL profile, matching
`ExpertAgent`'s existing fallback.

### 2. Kit specifications

Each kit is one section whose heading starts with `## 🧰 ` followed by a
pillar-appropriate label, so `DesignerAgent` can match the single
marker `🧰` while the label stays free.

- **checklist** — 6–8 items `- ☐ …`, each carrying: what to check /
  the normal value or threshold / what an out-of-range reading means.
- **questions** — 4–5 customer questions ordered broad → specific,
  plus 2 common objections with a verbatim reply line each.
- **calculator** — 1–2 formulas, the variables to ask the customer for,
  Thai reference figures (tariff, emission factor), and one worked
  substitution.

### 3. Prompt assembly — `TranslatorAgent`

The prompt becomes `BASE_RULES + profile sections + kit spec + assigned
scene`, replacing the single `PROMPT` constant. `BASE_RULES` keeps the
existing constraints: no greeting, no self-introduction, no tagline,
dash bullets only, no LaTeX, source-numbers-first, 800–1,000 words, and
the four anchors.

`Takeaways` is removed. The kit replaces it in the same position and
carries the Sales/Technical split internally where it is meaningful
(e.g. a question set contains both business and technical questions).

### 4. Scene assignment — deterministic, in code

`scene_for(date, industry, profile)` picks from the profile's pool by a
stable function of the date ordinal and industry, and excludes the
scenes used on the two previous publication dates. Same inputs always
yield the same scene, so the choice is testable; the model never picks.

The chosen scene is injected into the prompt and verified downstream
(see gate table below) so the model cannot silently fall back to the
familiar factory manager.

### 5. Renderer — `DesignerAgent`

Add one callout box for `<h2>🧰 …</h2>`, reusing the existing
`kcapture` box styling with a different accent colour. No other
renderer changes; `☐` needs none.

## Quality gates — `EditorAgent`

All checks are deterministic (regex/counting). A failure feeds the
existing single regeneration call, so the happy path adds no LLM cost.

| Gate | Rule |
|---|---|
| Anchors | all four anchor headings present |
| Kit present | a heading starting `## 🧰` exists |
| checklist | ≥6 lines matching `^- ☐ `, ≥3 of them containing number+unit |
| questions | ≥4 lines ending in `?`, ≥2 objection/reply pairs |
| calculator | ≥1 line containing `=`, ≥3 number+unit, one worked substitution |
| Scene used | the assigned scene's keyword appears in the article |
| Existing | LaTeX stripped, length gate, number+unit ≥3, no company names |

The `Takeaways` check (`editor_agent.py:113-114`) is replaced by the
kit-present check.

## Testing

Every test is written to fail first.

- Registry: all six pillars have sections, a kit, and ≥5 scenes.
- Assembly: each pillar's prompt contains the four anchors, that
  pillar's section titles, and its kit spec.
- Scene: same date+industry → same scene; three consecutive dates →
  three different scenes.
- Gates: one red and one green case per kit type, using text captured
  from real published articles as fixtures.
- Renderer: `## 🧰 …` becomes the callout box; `- ☐` survives to email,
  site HTML, and .docx.

## Rollout

1. Dry-run one article per pillar (six runs, ≈$0.2, no upload, no team
   email).
2. Email the two or three most different samples to the owner only.
3. On approval, merge; the team sees the new shape the next morning.
4. Rollback is `git revert` of the single merge commit.

## Risks

- **Depth loss:** the kit takes ~150 words from the 1,000-word budget.
  If articles thin out, raise the target to 1,100–1,200.
- **Regeneration loop cost:** stricter gates mean the editor's repair
  call fires more often. The dry-run round measures this before merge.
- **Anchor drift:** a future profile edit could drop an anchor. The
  assembly test covers all six profiles, so this fails in CI.
