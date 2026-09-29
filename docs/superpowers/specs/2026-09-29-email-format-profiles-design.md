# Per-Pillar Email Format Profiles — Design

**Date:** 2026-09-29
**Branch:** `chuan`
**Status:** Revised by panel review — amendments A1–A9 below supersede the
sections they name. Read "Panel review" before implementing anything.

> **Revision history**
> - **v1** — variety + one usable artifact per issue (sections above).
> - **v2 (this version)** — the owner added a goal v1 never served:
>   *readers must actually retain knowledge*. The panel found that v1
>   optimises delivery, not learning, and that nothing in the system
>   measures whether either works. Amendments A1–A9 apply.

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

---

# Panel review (2026-09-29)

New goal from the owner: *"อยากให้คนอ่านได้ความรู้จริง ๆ"* — readers must
retain knowledge, not just finish the email. v1 was written before that
goal existed and optimises variety plus a usable artifact.

## Evidence gathered before the panel sat

| Measurement | Source | Result |
|---|---|---|
| Glossary terms introduced | 8 published articles (09-18 → 09-29) | 31 distinct terms |
| Terms that reappear on a later day | same set | **2 of 31 (6%)** — `SEC`, `Parasitic Load` |
| Difficulty level reaching any writing prompt | `grep level src/agents/*.py` | **none** — `level=` is written by `planner_agent.py:76`, used only for filenames (`main.py`) and site grouping (`index_builder.py:58`) |
| Reinforcement of earlier material | `recap_agent.py:88-99` | summary only ("สรุปประจำสัปดาห์") — re-reading, no retrieval |
| Cross-article linking that exists | `index_builder.py:205-218` + `main.py:255-260` | same-cluster related links + stored TL;DR — a spacing rail already built, unused for recall |
| Interactive elements possible in email | `designer_agent.py:15,193` (premailer inlining; Gmail/Outlook targets) | none — no JS, and `<details>` is unreliable in Gmail |

## Seats

### 1. ผู้อ่านจริง — Sales engineer, 07:00, บนมือถือ, ก่อนเข้าไซต์งาน

| Severity | Finding |
|---|---|
| MAJOR | "ผมอ่าน 11 นาทีทุกเช้าไม่ไหวครับ" — v1 keeps the 800–1,000-word target and *adds* a kit on top. The reader already skims; a longer email lowers retention rather than raising it. |
| MAJOR | "อ่านจบแล้วถามผมว่าเมื่อวานเรื่องอะไร ผมตอบไม่ได้" — nothing in v1 ever asks the reader to recall anything. Recognition while reading feels like learning and is not. |
| MINOR | ศัพท์ใหม่ 4 คำทุกวัน ไม่เคยกลับมาอีก — 31 terms in 8 days, 2 reappear. That is a vocabulary firehose. |

### 2. นักออกแบบการเรียนรู้ (instructional design) — the seat the author is weakest in

| Severity | Finding |
|---|---|
| BLOCKER | v1 contains **no retrieval practice anywhere**. Format variety changes how the page looks; it does not change whether anything is encoded. The one intervention that reliably produces retention — being asked to *produce* an answer from memory after a delay — is absent from both the daily email and the Saturday recap (`recap_agent.py:88` is a summary). Ship v1 as written and the result is prettier emails with the same retention. |
| BLOCKER | The kit is **procedural, not conceptual**. A checklist says what to do without teaching why it works, so two weeks later the reader can neither reproduce nor adapt it. The owner's goal needs one transferable mental model per issue, stated explicitly, which the kit then exercises. |
| MAJOR | **No spacing.** Each issue is an island, yet `index_builder.related_articles()` already computes same-cluster neighbours and `__summaries.json` already stores their TL;DR — the rail for "revisit something from 3–14 days ago" exists and is unused. |
| MAJOR | **Cognitive load per issue:** two sections plus case, Consultant Move, kit, Knowledge Capture, four glossary terms and two formulas. Readers retain roughly one idea per session; v1 offers eight. |
| MINOR | `level` L1/L2/L3 exists in the calendar but never reaches a prompt, so a Level 3 issue reads exactly like a Level 1. Progression is decorative. |

### 3. ที่ปรึกษาพลังงานอาวุโส (domain)

| Severity | Finding |
|---|---|
| MAJOR | The **calculator kit invites fabricated authority**. v1 asks for "ตัวเลขอ้างอิงไทย (tariff, EF)" with no source of truth. A real sample already produced `Energy Intensity 2.5–4.5 GJ/ton ตามมาตรฐาน ISO 50001` — ISO 50001 specifies no such range. A consultant who quotes that to a customer is embarrassed, and it sits in the very part we tell them to use verbatim. |
| MAJOR | The TECHNICAL profile leads with "หน้างานบอกอะไร", but the pipeline has no site data, so the model will invent readings. Acceptable as an illustrative worked example, dangerous if written as fact — the framing must be explicit. |
| MINOR | The scene pool (hotel, hospital, contractor, CFO…) must stay inside PTT NGR ESP's real customer mix, or the team studies cases they never meet. |

### 4. วิศวกรผู้ดูแลระบบ (support — the person paged at 07:00)

| Severity | Finding |
|---|---|
| MAJOR | Any recall block must render in Gmail and Outlook with **no JS and no reliable `<details>`**. Hiding the answer has to be plain layout — answers in a separate box at the bottom — verified through `premailer` (`designer_agent.py:193`) like every other box. |
| MAJOR | v1 adds six deterministic gates feeding the single editor repair call. If a gate is unsatisfiable for a given topic (e.g. "≥3 checklist items with number+unit" on a soft-skill day) the repair fires every single day, costing a call and ~30s, and nobody notices because the run stays green. Needs a per-kit sanity bound plus a log line whenever repair fires. |
| MINOR | One more thing to explain at 07:00: "why is today's email a quiz?" The change needs a one-line note to the team on day one. |

### 5. นักวัดผล (measurement)

| Severity | Finding |
|---|---|
| BLOCKER | **Nothing in the system can tell whether any of this works.** The only signal today is the owner's impression (n=1). No opens, no clicks, no replies counted, no answers collected. Ship v1 or v2 and the honest report next month is "we cannot say" — any claim of improvement would be unfalsifiable. |
| MAJOR | The success criterion must be observable and carry a denominator — e.g. *replies to the Saturday retrieval mail: k of 17 recipients*, tracked weekly — not "อีเมลดีขึ้น". |
| MINOR | The baseline must be captured **before** the change (current replies ≈ 0 of 17), or there is nothing to compare against afterwards. |
| — | **Superseded 2026-09-29:** the owner ruled the mail stays one-way, so the reply-based criterion this seat proposed is not built. See C2 and the revised A8: retention is recorded as permanently unmeasured, and only delivery-side numbers are logged. |

### 6. ผู้ดูแลโค้ด (maintainer)

| Severity | Finding |
|---|---|
| MAJOR | A recall block needs *past* content at generation time. `index_builder` reads Drive and `__summaries.json`; pulling two items is cheap, but the failure path must silently degrade — skip the block — because `EmailNotSentError` now makes failures loud, and a Drive hiccup must not cost the team its daily email. |
| MINOR | Six profiles × sections × kit × scenes is a lot of prose in one module. Keep `formats.py` data-only with no logic, so editing a profile cannot break assembly. |
| NOTE | Cost: recall questions should be produced inside the existing translator call by passing past TL;DRs into that prompt, not by adding a seventh call. |

## Tally

| Severity | Count |
|---|---|
| BLOCKER | 3 |
| MAJOR | 11 |
| MINOR | 6 |
| NOTE | 1 |

## Conflicts and resolutions

**C1 — the reader wants shorter; the domain and instructional seats want depth and a worked example.**
Resolution: **re-allocate, do not extend.** The core article drops to
600–700 words built around one mental model; kit ~150 words; recall
block ~80 words. The total lands near today's 900–1,000, so nothing gets
longer, but half the words now do teaching work instead of covering
ground.

**C2 — measurement wants a feedback channel; support wants no new infrastructure; the owner requires the mail stay one-way.**
Resolution (owner decision, 2026-09-29): **no reply channel.** The mail
asks nothing of the reader and collects nothing. That makes retention
itself unmeasurable with the rails available — tracking pixels are
blocked by corporate mail clients, and the static site stores nothing —
so the spec states it plainly rather than inventing a proxy for
learning. What the pipeline *can* measure about itself is logged
instead (see A8), and no such number may be presented as evidence that
people learned more.

**C3 — the instructional seat wants spaced recall; the maintainer warns that its data comes from Drive at generation time.**
Resolution: the recall block is **best-effort**. If `__summaries.json`
or Drive is unavailable the block is omitted and the run continues; a
missing recall block is never an error.

## Amendments (binding — each supersedes the section it names)

**A1 — supersedes "Goals".** The primary goal becomes: *a reader can
answer a question about an article 3–14 days after reading it.* Variety
and the kit are means, not ends.

**A2 — supersedes "Design §1/§3".** Every issue states **one mental
model** ("หลักคิดวันนี้") in ≤2 sentences immediately after
`💡 ประเด็นวันนี้`. Both middle sections must serve that model; whatever
does not serve it is cut. One idea per issue, not eight.

**A3 — new section; supersedes the ordering in "Design §2".** Add a
recall block `## 🔁 ทวนของเก่า` carrying **two questions drawn from
articles 3–14 days old**, sourced from `__summaries.json` and
`related_articles()` (same cluster first). Answers are not inline — they
render in a separate box at the very bottom, after the glossary.
Best-effort per C3, and no extra LLM call: past TL;DRs go into the
existing translator prompt.

**A4 — supersedes "Non-Goals" (recap exclusion).** The Saturday recap
changes from summary to **retrieval**: five questions about the week
with the answers in a box below, so the reader tests themselves and
checks immediately. The mail stays **one-way — it asks for no reply**
(owner decision, C2). The prompt at `recap_agent.py:88-99` is rewritten;
the `Knowledge Capture` anchor stays, so renderer and site are
unaffected.

**A5 — supersedes the length rule in "Design §3".** Targets become body
600–700 words, kit ~150, recall ~80. The editor length gate moves with
them.

**A6 — supersedes the profile fields in "Design §1".** `topic["level"]`
is passed into the translator prompt with an explicit meaning: L1 =
first encounter (define terms, one example), L2 = apply (worked example
with numbers), L3 = judge (trade-offs, when it fails). If a level never
changes the text, it is removed from the calendar instead of being kept
as decoration.

**A7 — supersedes "Kit specifications" (calculator).** Every reference
number in a kit carries its source inline (`— ที่มา: PEA tariff 2569`).
Numbers without a source are not allowed, and the editor gate rejects a
calculator kit whose reference figures lack a source tag. A curated
`docs/references/th-energy-reference.md` holds the approved figures and
is quoted into the prompt, so the model recalls rather than invents.

**A8 — supersedes "Testing"; adds a measurement requirement.**
*(Revised 2026-09-29 after the owner ruled the mail stays one-way.)*
Retention is **not measured and cannot be** with one-way delivery — no
replies, no pixels (corporate clients block images), no storage (the
site is static GitHub Pages). The spec records this as a permanent
`NOT VERIFIED`, and nobody may claim "the team learns more" from any
number produced here.

*(Revised again 2026-09-29, owner: "ไม่เป็นไร ขอให้เนื้อหามันดี คนจะค่อย ๆ
ได้เอง" — so no human-run measurement ritual either. A weekly log nobody
fills in is worse than none: it rots and then gets quoted.)*

The run prints **one line at the end of each daily run**, for operations
rather than for proof:

```
📐 shape=SOFTSKILL kit=questions recall=2 repairs=0
```

It exists to catch an operational fault, not to evidence learning: a
gate that is unsatisfiable for some pillar shows up as `repairs=1` every
day, burning an LLM call and ~30s silently (seat 4 MAJOR). Nothing is
aggregated, nothing is filed weekly, and no number from this line may be
presented as evidence that anyone learned anything.

Quality, not measurement, carries the retention goal: A2 (one mental
model), A3 (spaced recall), A6 (level-appropriate depth) and A7 (sourced
numbers) are the levers, and the six-pillar dry-run before merge is
where a human judges whether the content is actually good.

**A9 — supersedes "Design §5".** No `<details>`, no JS. The recall box
and the answer box are ordinary table-based boxes rendered through
`premailer`, and a test asserts both survive inlining.

## Deferred / not accepted

| Idea | Why not |
|---|---|
| Interactive quiz with scoring | Needs a backend; the site is static GitHub Pages and stores nothing. |
| Per-reader personalisation (adaptive difficulty) | No per-reader data exists, and collecting it needs infrastructure the team does not have. |
| Cutting the email to ~300 words | Kills the depth the domain seat requires; C1's re-allocation reaches the reader's goal without it. |
| Tracking pixels / open rates | Corporate mail clients block images by default, so the number would be wrong — and would still be quoted as if it were right. |
| Letting the model choose the outline per day (approach B) | Rejected before the panel: extra call, weaker control, silent anchor loss. |
| Daily quiz instead of weekly | Retrieval on brand-new material tests reading comprehension, not memory; spacing needs a gap. |

## Re-planning

No implementation plan exists yet, so nothing needs re-planning. The
plan must be written from v1 **as amended by A1–A9**.
