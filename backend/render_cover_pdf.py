# backend/render_cover_pdf.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Tuple
import re

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _split_md_bold(text: str) -> List[Tuple[str, bool]]:
    s = text or ""
    out: List[Tuple[str, bool]] = []
    pos = 0
    for m in _BOLD_RE.finditer(s):
        if m.start() > pos:
            out.append((s[pos:m.start()], False))
        out.append((m.group(1), True))
        pos = m.end()
    if pos < len(s):
        out.append((s[pos:], False))
    return out


class _Layout:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.left = 50
        self.right = 50
        self.top = 50
        self.bottom = 55
        self.line_gap = 13

    @property
    def start_y(self) -> float:
        return self.height - self.top


class _Pen:
    def __init__(self, c: canvas.Canvas, layout: _Layout):
        self.c = c
        self.layout = layout
        self.x = layout.left
        self.y = layout.start_y

    def _ensure_space(self, lines: int = 1) -> None:
        if self.y - (lines * self.layout.line_gap) < self.layout.bottom:
            self.c.showPage()
            self.x = self.layout.left
            self.y = self.layout.start_y

    def blank(self, n: float = 1.0) -> None:
        self._ensure_space(max(1, int(n)))
        self.y -= self.layout.line_gap * n

    def line(self, text: str, font: str = "Helvetica", size: int = 11) -> None:
        self._ensure_space(1)
        self.c.setFont(font, size)
        self.c.drawString(self.x, self.y, text)
        self.y -= self.layout.line_gap

    def rich_paragraph(self, text: str, size: int = 11) -> None:
        max_w = (self.layout.width - self.layout.right) - self.x
        words: List[Tuple[str, bool]] = []

        for seg, bold in _split_md_bold(text):
            for w in re.split(r"(\s+)", seg):
                if w:
                    words.append((w, bold))

        def word_width(word: str, is_bold: bool) -> float:
            font = "Helvetica-Bold" if is_bold else "Helvetica"
            return pdfmetrics.stringWidth(word, font, size)

        line_items: List[Tuple[str, bool]] = []
        line_w = 0.0

        def flush() -> None:
            nonlocal line_items, line_w
            if not line_items:
                return

            self._ensure_space(1)
            cursor = self.x
            for txt, is_bold in line_items:
                font = "Helvetica-Bold" if is_bold else "Helvetica"
                self.c.setFont(font, size)
                self.c.drawString(cursor, self.y, txt)
                cursor += pdfmetrics.stringWidth(txt, font, size)

            self.y -= self.layout.line_gap
            line_items = []
            line_w = 0.0

        for w, is_bold in words:
            if not line_items and w.isspace():
                continue

            ww = word_width(w, is_bold)
            if line_items and (line_w + ww) > max_w:
                flush()
                if w.isspace():
                    continue

            line_items.append((w, is_bold))
            line_w += ww

        flush()


def render_cover_pdf(
    out_path: str | Path,
    cv: Dict[str, Any],
    cover_letter: str,
    company: str = "",
    job_title: str = "",
) -> Path:
    """
    Render cover letter PDF.

    Accepts company/job_title to stay compatible with backend/api.py,
    even if the current layout uses mostly header + body content.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out_path), pagesize=A4)
    width, height = A4
    pen = _Pen(c, _Layout(width, height))

    header = cv.get("header") if isinstance(cv.get("header"), dict) else {}
    name = (header.get("name") or "").strip()
    email = (header.get("email") or "").strip()
    phone = (header.get("phone") or "").strip()
    linkedin = (header.get("linkedin") or "").strip()
    github = (header.get("github") or "").strip()
    address = (header.get("address") or header.get("location") or "").strip()

    # Header
    if name:
        pen.line(name, font="Helvetica-Bold", size=14)

    for line in [
        f"Phone: {phone}" if phone else "",
        f"Email: {email}" if email else "",
        f"LinkedIn: {linkedin}" if linkedin else "",
        f"GitHub: {github}" if github else "",
        f"Address: {address}" if address else "",
    ]:
        if line:
            pen.line(line, font="Helvetica", size=10)

    pen.blank(0.8)

    # Optional role/company reference line
    role_company_line = " | ".join(
        [x for x in [job_title.strip(), company.strip()] if x]
    )
    if role_company_line:
        pen.line(role_company_line, font="Helvetica-Oblique", size=10)
        pen.blank(0.5)

    # Body
    for raw in (cover_letter or "").split("\n\n"):
        txt = raw.strip()
        if not txt:
            continue
        pen.rich_paragraph(txt, size=11)
        pen.blank(0.6)

    c.save()
    return out_path