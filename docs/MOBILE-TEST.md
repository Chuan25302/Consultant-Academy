# Mobile + Accessibility Verification Checklist

ใช้ checklist นี้หลัง deploy ทุกครั้งที่แก้ template email หรือ DOCX
รัน manual บน Gmail iOS + Android เพื่อจับ rendering issue ที่ unit test
จับไม่ได้

## A. Pre-deploy: WCAG AA contrast (automated)

ทุก color pair ใน [src/agents/designer_agent.py](../src/agents/designer_agent.py)
ผ่าน WCAG AA (≥4.5:1 สำหรับ body text) ตาม baseline ด้านล่าง

| Pair | Ratio | Status |
|---|---|---|
| Body `#333` on `#FFF` | 12.63 | PASS |
| White on FRAMEWORK `#1B5E20` | 7.87 | PASS |
| White on TECHNICAL `#0D47A1` | 8.63 | PASS |
| White on COMPLIANCE `#B71C1C` | 6.57 | PASS |
| White on SUSTAINABILITY `#2E7D32` | 5.13 | PASS |
| White on RECAP `#37474F` | 9.65 | PASS |
| **White on INDUSTRY `#BF360A`** | **5.60** | **PASS** (เคยเป็น `#E65100` 3.79 — แก้แล้ว) |
| White on SOFTSKILL `#4A148C` | 11.86 | PASS |
| Glossary `#555` on `#F5F5F5` | 6.84 | PASS |
| Footer `#546E7A` on `#ECEFF1` | 4.68 | PASS |
| Footer link FRAMEWORK | 6.81 | PASS |
| Footer link INDUSTRY (NEW) | 4.85 | PASS |
| Footer link SUSTAINABILITY | 4.44 | borderline AA (≥3 = AA large text) |

> **ตรวจซ้ำเมื่อ:** เพิ่ม pillar ใหม่ หรือเปลี่ยน color/rgba ใน `PILLAR_CONFIG`
>
> **ตรวจวิธี:** รัน contrast snippet ในตอนท้ายของไฟล์นี้ หรือใช้
> [webaim.org/resources/contrastchecker](https://webaim.org/resources/contrastchecker/)

## B. Mobile Gmail rendering (manual, post-deploy)

### Setup
1. ส่งให้ตัวเอง: `python src/main.py --date YYYY-MM-DD` (ไม่ใส่ --dry-run)
2. เปิดบนทั้ง 2 platforms (Gmail iOS app + Gmail Android app)
3. หากใช้ outlook ในที่ทำงาน — เปิด Outlook desktop + Outlook mobile ด้วย

### Daily email (Mon-Fri)

- [ ] **Inbox preview** แสดง TL;DR ("ประเด็นวันนี้") ไม่ใช่คำทักทาย
- [ ] **Subject line** อ่านได้เต็ม `[PILLAR · weekday] หัวข้อ` ไม่ตัดกลาง
- [ ] **Header** pillar tag + level badge + industry badge อยู่ในแถวเดียวกัน ไม่ wrap แปลก
- [ ] **Header** ตัวเลข "อ่าน N นาที" สอดคล้องกับเนื้อหา (ไม่ใช่ 5 นาทีทุกวัน)
- [ ] **TL;DR section** "💡 ประเด็นวันนี้" สีเด่น border-left ตาม pillar
- [ ] **Bullets** render เป็น `•` หรือ list dot ทุกที่ ไม่ใช่ raw `*` หรือ `-`
- [ ] **Customer quote** ใน Complication เป็น blockquote มี border-left
- [ ] **Consultant Move** กล่องเขียวอ่อน (ไม่หายไปบนมือถือ)
- [ ] **Takeaways** "ทีม Sales:" + "ทีม Technical:" แสดง bold หัวข้อ + bullet ใต้
- [ ] **Glossary box** ที่ปลายเป็น list ของศัพท์ (1 บรรทัด/ศัพท์) ไม่ wrap แปลก
- [ ] **Footer related links** 1-3 link ใช้งานได้ → คลิกเปิด Drive ได้
- [ ] **Mission italic** "ยกระดับทีมจากผู้เชี่ยวชาญ..." แสดงข้างใต้ links
- [ ] **Dark mode** (ลอง switch เปิด): white text บน gradient header ยังอ่านได้

### Friday recap email

- [ ] **Subject** `[RECAP · เสาร์] สัปดาห์ที่ N`
- [ ] **Header** ใหญ่กว่า daily — "WEEK N" ตัวใหญ่ + range วันที่
- [ ] **Timeline strip** 5 cells (จ/อ/พ/พฤ/ศ) แสดงครบ ไม่ stack แปลก
- [ ] แต่ละ cell แสดงหัวข้อสั้นๆ (truncated ถ้ายาว)
- [ ] บนหน้าจอ ≤375px (iPhone SE) cells ยังอ่านได้

### DOCX (KB archive)

เปิดไฟล์ `[L1] YYYY-MM-DD topic.docx` ใน Word + Google Docs + LibreOffice:

- [ ] **Cover page**: pillar tag (FRAMEWORK), title สีตาม pillar, subtitle, Thai date
- [ ] **Heading 2/3** ใช้สี pillar (ไม่ใช่ default ดำ)
- [ ] **Bullets** render เป็น list (ไม่ใช่ raw text)
- [ ] **Bold runs** หนาจริง (ไม่ใช่ `**` literal)
- [ ] **Customer quote** เป็น "Intense Quote" style (italic + indent)
- [ ] **อ่านเพิ่มในชุดเดียวกัน** ที่ท้ายไฟล์มี link ใช้งานได้

## C. Cost regression check

หลัง deploy 1 อาทิตย์เต็ม:

```bash
# ดู cost ทุกวันใน data/cost.log
grep "$(date +%Y-%m)" data/cost.log | awk '{sum+=$NF} END {print "Month: $", sum}'
```

- [ ] รวมต่อเดือน <$2 (target ใน CLAUDE.md)
- [ ] ไม่มี MAX_TOKENS warning ใน logs (ถ้ามี = max_tokens ต้องดันขึ้นอีก)

## D. Snippet: contrast checker (Python)

```python
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def luminance(rgb):
    def chan(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)

def contrast(c1, c2):
    L1, L2 = luminance(hex_to_rgb(c1)), luminance(hex_to_rgb(c2))
    return (max(L1, L2) + 0.05) / (min(L1, L2) + 0.05)

# Body text ต้อง ≥4.5, large text (≥18pt) ≥3.0
print(contrast("#FFFFFF", "#BF360A"))  # 5.60 ✓
```
