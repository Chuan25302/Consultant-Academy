# Google Drive Setup Checklist

ก่อนรันระบบ ต้องเตรียม Drive 5 อย่าง สรุปท้ายเอกสาร — แต่ละอย่างใช้เวลา ~1 นาที

---

## ✅ Manual setup (ทำเองใน Drive)

### 1. สร้าง 3 folders
ที่ `My Drive` หรือ `Shared Drive` — ใส่ใน parent folder ก็ได้เพื่อความเป็นระเบียบ:

```
PTT NGR ESP Consultant Academy/   ← parent (optional)
├── 📁 Email Archives/
├── 📁 Knowledge Base/
└── 📁 Program Management/
```

วิธีสร้าง: Drive → **+ New** → **Folder** → ตั้งชื่อ

### 2. Upload calendar file
- เปิด `docs/Content-Calendar-2024.md` จาก repo
- Drag & drop เข้า Drive (อยู่ไหนก็ได้)
- **เลือก "Keep as Markdown"** ถ้า Drive ถามจะแปลงเป็น Google Doc
  - ถ้าเผลอกด convert ระบบยังอ่านได้ — มี auto-detect

### 3. Share กับ Service Account email
หา SA email จาก `service-account.json`:
```json
{
  "client_email": "consultant-academy-bot@your-project.iam.gserviceaccount.com",
  ...
}
```

แต่ละ folder + calendar file → คลิกขวา → **Share** → ใส่ SA email → **Editor**

> 💡 **Tip**: ถ้า 3 folders อยู่ใน parent folder → share **parent** เดียว แล้ว subfolders inherit ทั้งหมด ประหยัดเวลา

### 4. เก็บ IDs ลง `.env`
หา ID จาก URL:
- Folder: `drive.google.com/drive/folders/`**`<ID>`**
- File: `drive.google.com/file/d/`**`<ID>`**`/view`

```bash
CALENDAR_FILE_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz1234567
FOLDER_EMAIL_ARCHIVES=1AbCdEfGhIjKlMnOpQrStUvWxYz1234567
FOLDER_KNOWLEDGE_BASE=1AbCdEfGhIjKlMnOpQrStUvWxYz1234567
FOLDER_PROGRAM_MGMT=1AbCdEfGhIjKlMnOpQrStUvWxYz1234567
```

### 5. Test ว่า SA เข้าถึงได้
```bash
python src/main.py --dry-run
```

จะเห็น output:
```
🔎 Validating Drive access...
  ✓ CALENDAR_FILE_ID → Content-Calendar-2024.md
  ✓ FOLDER_EMAIL_ARCHIVES → Email Archives
  ✓ FOLDER_KNOWLEDGE_BASE → Knowledge Base
  ✓ FOLDER_PROGRAM_MGMT → Program Management
🧪 [dry-run] would upload: ...
```

---

## 🤖 Auto-created (ไม่ต้องทำเอง)

หลัง first run system จะสร้างให้:

```
📁 Email Archives/                       ← user สร้าง
└── 📁 2024/                             ← auto
    ├── 📁 may/
    │   ├── [Email] 2024-05-06 Chiller 101.html
    │   ├── [Email] 2024-05-07 Hotel Profile.html
    │   └── [Recap] 2024-05-11 สัปดาห์ที่ 1.html
    └── 📁 june/

📁 Knowledge Base/                       ← user สร้าง
├── 📄 00-Master-Index.md                ← auto regenerate ทุกวัน
├── 📁 01-Technical-Depth/
│   ├── 📁 HVAC-Chillers/
│   │   ├── [L1] 2024-05-06 Chiller Efficiency 101.docx
│   │   └── [L2] 2024-09-12 Cooling Tower.docx
│   ├── 📁 Motors-VFD/
│   ├── 📁 Steam/
│   ├── 📁 Compressed-Air/
│   ├── 📁 Cooling-Tower/
│   └── 📁 Pumps/
├── 📁 02-Industry-Business-Logic/
│   ├── 📁 Hospitality/
│   ├── 📁 Steel/
│   ├── 📁 Pharma/
│   ├── 📁 Auto-OEM/
│   ├── 📁 Electronics-HDD/
│   └── 📁 Hospitals/
├── 📁 03-Diagnostic-Frameworks/
│   ├── 📁 Energy-Audit/
│   ├── 📁 Measurement-Verification/
│   └── 📁 Financial-Analysis/
├── 📁 04-Soft-Skills-Positioning/
│   ├── 📁 Discovery/
│   ├── 📁 Objection-Handling/
│   └── 📁 Negotiation/
├── 📁 05-Standards-Compliance/
│   ├── 📁 ISO-50001/
│   ├── 📁 GMP/
│   ├── 📁 HACCP/
│   ├── 📁 Thai-Energy-Law/
│   └── 📁 Thai-TIS/
└── 📁 06-Sustainability-Carbon/
    ├── 📁 GHG-Accounting/
    ├── 📁 T-VER/
    ├── 📁 CBAM/
    ├── 📁 RE100/
    └── 📁 Net-Zero/
```

Cluster names มาจาก field `cluster=...` ในปฏิทิน — เพิ่ม cluster ใหม่ในปฏิทิน folder ใหม่ก็สร้างเองอัตโนมัติ

---

## 🆔 Get Service Account email

ถ้ายังไม่มี service account:

1. https://console.cloud.google.com → เลือก project (หรือสร้างใหม่)
2. **Enable APIs** → ค้น "Google Drive API" → Enable
3. **IAM & Admin** → **Service Accounts** → **+ Create Service Account**
   - Name: `consultant-academy-bot`
   - Role: skip (ไม่ต้อง grant ที่นี่ — ไป share folder แทน)
4. Service Account ใหม่ → tab **Keys** → **Add Key** → **Create new key** → **JSON**
   - ดาวน์โหลด JSON → save as `service-account.json` ใน repo root
5. Copy email จาก JSON file (`client_email` field) — เอาไป share folders

---

## 📌 Tips

### ใช้ Shared Drive (แนะนำ)
- ✅ ทีมทุกคนเข้าถึงได้ทั้งหมด ไม่ต้อง share รายไฟล์
- ✅ ไฟล์ไม่หายถ้า owner ลาออก
- ⚠️ Service Account ต้อง add เป็น **Content manager** ขึ้นไป

### Quota ของ Service Account
- Service Account ไม่มี Drive ของตัวเอง = ไฟล์ทั้งหมดใช้ quota ของ folder owner
- ถ้า owner เป็น Workspace user → quota ใหญ่ ไม่ต้องกังวล
- ถ้า owner เป็น personal Gmail → 15 GB free, อาจหมดเร็วถ้า upload เยอะ
  → solution: ใช้ Shared Drive ใน Workspace

### ถ้าอยากให้ทีม edit ปฏิทินได้
- Share `Content-Calendar-2024.md` กับทีมเป็น Editor ด้วย
- ระบบจะอ่าน version ล่าสุดจาก Drive ทุกวัน — แก้ปฏิทินมีผลเลย

### ถ้าอยากให้ทีมแค่อ่าน Knowledge Base
- Share `Knowledge Base/` กับทีมเป็น **Viewer**
- ผู้อ่านเปิด `00-Master-Index.md` ใน browser → คลิก link → อ่าน DOCX

---

## ✓ Setup Checklist

```
□ สร้าง folder "Email Archives"
□ สร้าง folder "Knowledge Base"
□ สร้าง folder "Program Management"
□ Upload Content-Calendar-2024.md
□ มี service-account.json อยู่ใน repo root
□ Share ทั้ง 3 folders + calendar file กับ SA email (Editor)
□ Copy folder/file IDs ลง .env
□ Run `python src/main.py --dry-run` ผ่าน (validation ✓)
```

ครบ checklist = พร้อมรัน production
