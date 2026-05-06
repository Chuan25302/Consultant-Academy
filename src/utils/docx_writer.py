"""
Naive Markdown -> DOCX bytes for the Knowledge Base archive.
Handles: ## h2, ### h3, **bold**, - bullets, plain paragraphs.
"""
import io
import re

from docx import Document


def markdown_to_docx_bytes(md: str, title: str = "") -> bytes:
    doc = Document()
    if title:
        doc.add_heading(title, level=0)

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            doc.add_paragraph("")
            continue
        if line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            _add_runs(p, line[2:])
        else:
            p = doc.add_paragraph()
            _add_runs(p, line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _add_runs(paragraph, text: str):
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)
