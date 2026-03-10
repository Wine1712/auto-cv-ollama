# backend/render_pdf.py
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


# ============================================================
# Public API
# ============================================================
def render_pdf(out_path: str | Path, cv: Dict[str, Any]) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out_path), pagesize=A4)
    width, height = A4

    layout = _Layout(width=width, height=height)
    pen = _Pen(c, layout)

    # ---------- Header ----------
    header = _as_dict(cv.get("header"))
    _render_header_block(pen, header, cv)

    # ---------- Professional Summary ----------
    summary = (cv.get("summary") or "").strip()
    if summary:
        pen._ensure_space(1)
        pen._draw_left_text("PROFESSIONAL SUMMARY", font="Helvetica-Bold", size=11)
        pen.y -= pen.layout.line_gap * 0.9

        for line in summary.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = _split_md_bold(line)
            pen.rich_line(parts, size=10)

        pen.blank(0.55)

    # ---------- Areas of Expertise ----------
    areas = _as_list(cv.get("areas_of_expertise"))
    if areas:
        pen.section("AREAS OF EXPERTISE")
        clean = [str(x).strip() for x in areas if str(x).strip()]
        if clean:
            pen.paragraph(" • ".join(clean), size=10)
            pen.blank(0.1)
        pen.blank(0.45)

    # ---------- Career Highlights ----------
    highlights = _as_list(cv.get("career_highlights"))
    if highlights:
        pen.section("CAREER HIGHLIGHTS")
        clean = [str(x).strip() for x in highlights if str(x).strip()]
        if clean:
            pen.two_column_bullets(clean, size=9.8)
        pen.blank(0.35)

    # ---------- Skills ----------
    skills = _as_dict(cv.get("skills"))
    if skills:
        pen.section("SKILLS")
        for cat, items in skills.items():
            if not items:
                continue
            if isinstance(items, list):
                line = ", ".join([str(x).strip() for x in items if str(x).strip()])
            else:
                line = str(items).strip()
            if line:
                pen.paragraph(f"**{cat}:** {line}", size=10)
                pen.blank(0.08)
        pen.blank(0.4)

    # ---------- Work Experience ----------
    experience = _as_list_of_dicts(cv.get("experience"))
    if experience:
        pen.section("WORK EXPERIENCE")
        for item in experience:
            _render_experience_item(pen, item)
        pen.blank(0.15)

    # ---------- Projects ----------
    projects = _as_list_of_dicts(cv.get("projects"))
    if projects:
        pen.section("PROJECTS")
        for item in projects:
            _render_project_item(pen, item)
        pen.blank(0.15)

    # ---------- Education ----------
    education = _as_list_of_dicts(cv.get("education"))
    if education:
        pen.section("EDUCATION")
        for ed in education:
            _render_education_item(pen, ed)
        pen.blank(0.15)

    # ---------- Certifications ----------
    certs_any = cv.get("certifications")
    if certs_any:
        pen.section("CERTIFICATIONS")
        _render_certifications(pen, certs_any)
        pen.blank(0.15)

    # ---------- Internships ----------
    internships = _as_list_of_dicts(cv.get("internships"))
    if internships:
        pen.section("INTERNSHIPS")
        for item in internships:
            _render_internship_item(pen, item)
        pen.blank(0.15)

    c.save()
    return out_path


# ============================================================
# Header block
# ============================================================
def _render_header_block(pen: "_Pen", header: Dict[str, Any], cv: Dict[str, Any]) -> None:
    name_raw = (header.get("name") or "").strip()
    name = _strip_md_bold_markers(name_raw) or "CANDIDATE NAME"

    title = str(header.get("title") or cv.get("title") or "").strip()
    phone = (header.get("phone") or "").strip()
    email = (header.get("email") or "").strip()
    linkedin = (header.get("linkedin") or "").strip()
    github = (header.get("github") or "").strip()
    address = (header.get("address") or header.get("location") or "").strip()

    pen.title(name.upper())

    if title:
        pen.center_line(title, size=11)
        pen.blank(0.15)

    line1_parts = [x for x in [address, email, phone] if x]
    if line1_parts:
        pen.center_line(" | ".join(line1_parts), size=9.2)

    line2_parts = [x for x in [github, linkedin] if x]
    if line2_parts:
        pen.center_line(" | ".join(line2_parts), size=9.2)

    pen.rule()
    pen.blank(0.8)


# ============================================================
# Section items
# ============================================================
def _render_education_item(pen: "_Pen", ed: Dict[str, Any]) -> None:
    degree = (ed.get("degree") or "").strip()
    uni = (ed.get("university") or "").strip()
    city = (ed.get("city") or "").strip()
    country = (ed.get("country") or "").strip()

    dates = (ed.get("dates") or "").strip()
    if not dates:
        dates = _join_dates((ed.get("start") or "").strip(), (ed.get("end") or "").strip())

    coursework = (ed.get("coursework") or "").strip()
    honors = (ed.get("honors") or "").strip()

    if degree:
        pen.bold_line(degree, size=10)
    else:
        line = (ed.get("line") or "").strip()
        if line:
            pen.bold_line(line, size=10)

    left = _join_nonempty([uni, _join_nonempty([city, country], sep=", ")], sep=", ").strip(", ").strip()
    if left or dates:
        pen.left_right_line(left, dates, left_font="Helvetica-Oblique", right_font="Helvetica", size=10)

    if coursework:
        pen.bullet(f"Relevant Coursework: {coursework}", size=9.8)
    if honors:
        pen.bullet(f"Honors: {honors}", size=9.8)

    pen.blank(0.18)


def _render_experience_item(pen: "_Pen", item: Dict[str, Any]) -> None:
    role = (item.get("role") or "").strip()
    company = (item.get("company") or "").strip()
    dates = (item.get("dates") or "").strip()
    if not dates:
        dates = _join_dates((item.get("start") or "").strip(), (item.get("end") or "").strip())

        pen.left_right_rich(role or "Experience", dates, left_bold=True, right_bold=False, size=10.5)

    if company:
        pen.line(company, font="Helvetica-Oblique", size=10)

    bullets_list = _coerce_bullets(item.get("bullets") or item.get("description") or [])
    for b in bullets_list:
        pen.bullet(b, size=9.8)

    pen.blank(0.22)


def _render_project_item(pen: "_Pen", item: Dict[str, Any]) -> None:
    name = (item.get("name") or "").strip() or "Project"
    tech = (item.get("tech") or "").strip()
    dates = (item.get("dates") or "").strip()
    if not dates:
        dates = _join_dates((item.get("start") or "").strip(), (item.get("end") or "").strip())

    pen.left_right_rich(name, dates, left_bold=True, right_bold=False, size=10)

    if tech:
        pen.paragraph(f"**Technologies:** {tech}", size=9.8)

    bullets_list = _coerce_bullets(item.get("bullets") or item.get("description") or [])
    for b in bullets_list:
        pen.bullet(b, size=9.8)

    pen.blank(0.22)


def _render_internship_item(pen: "_Pen", item: Dict[str, Any]) -> None:
    role = (item.get("role") or "").strip()
    company = (item.get("company") or "").strip()

    dates = (item.get("dates") or "").strip()
    if not dates:
        dates = _join_dates((item.get("start") or "").strip(), (item.get("end") or "").strip())

    pen.left_right_rich(role or "Internship", dates, left_bold=True, right_bold=False, size=10)

    if company:
        pen.line(company, font="Helvetica-Oblique", size=10)

    bullets_list = _coerce_bullets(item.get("bullets") or item.get("description") or [])
    for b in bullets_list:
        pen.bullet(b, size=9.8)

    pen.blank(0.22)


def _render_certifications(pen: "_Pen", certs_any: Any) -> None:
    if not certs_any:
        return

    if isinstance(certs_any, list) and certs_any and isinstance(certs_any[0], dict):
        for c in certs_any:
            title = (c.get("title") or c.get("name") or "").strip()
            issuer = (c.get("issuer") or "").strip()

            dates = (c.get("dates") or "").strip()
            if not dates:
                dates = _join_dates((c.get("start") or "").strip(), (c.get("end") or "").strip())

            left = title or "Certification"
            if issuer:
                left = f"{left} — {issuer}"

            pen.bullet_left_right(left, dates, size=9.8)

        pen.blank(0.18)
        return

    if isinstance(certs_any, list):
        for x in certs_any:
            s = str(x).strip()
            if s:
                pen.bullet(s, size=9.8)
        pen.blank(0.18)
        return

    s = str(certs_any).strip()
    if s:
        pen.bullet(s, size=9.8)
        pen.blank(0.18)


# ============================================================
# PDF layout + drawing utilities
# ============================================================
class _Layout:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.left = 42
        self.right = 42
        self.top = 36
        self.bottom = 45
        self.line_gap = 14

    @property
    def usable_width(self) -> float:
        return self.width - self.left - self.right

    @property
    def start_y(self) -> float:
        return self.height - self.top


class _Pen:
    _BOLD_RE = re.compile(r"(\*\*.*?\*\*)")

    def __init__(self, c: canvas.Canvas, layout: _Layout):
        self.c = c
        self.layout = layout
        self.x = layout.left
        self.y = layout.start_y

    # ---------- paging ----------
    def _ensure_space(self, lines: int = 1) -> None:
        needed = lines * self.layout.line_gap
        if self.y - needed < self.layout.bottom:
            self.c.showPage()
            self.x = self.layout.left
            self.y = self.layout.start_y

    def blank(self, n_lines: float = 1.0) -> None:
        self._ensure_space(max(1, int(n_lines)))
        self.y -= self.layout.line_gap * n_lines

    # ---------- headings ----------
    def title(self, text: str) -> None:
        self._ensure_space(2)
        self._draw_center_text(text, font="Helvetica-Bold", size=17)
        self.y -= self.layout.line_gap * 1.0

    def section(self, text: str) -> None:
        self._ensure_space(2)
        self._draw_left_text(text, font="Helvetica-Bold", size=11)
        self.y -= self.layout.line_gap * 0.55
        self.rule(light=True)
        self.y -= self.layout.line_gap * 0.35

    def rule(self, light: bool = False) -> None:
        self._ensure_space(1)
        y = self.y
        self.c.setLineWidth(0.45 if light else 0.7)
        self.c.line(self.layout.left, y, self.layout.width - self.layout.right, y)
        self.y -= self.layout.line_gap * 0.55

    # ---------- simple lines ----------
    def center_line(self, text: str, size: int = 9) -> None:
        self._ensure_space(1)
        self._draw_center_text(text, font="Helvetica", size=size)
        self.y -= self.layout.line_gap * 0.88

    def line(self, text: str, font: str = "Helvetica", size: int = 10) -> None:
        self._ensure_space(1)
        self.c.setFont(font, size)
        self.c.drawString(self.x, self.y, text)
        self.y -= self.layout.line_gap * 0.95

    def bold_line(self, text: str, size: int = 10) -> None:
        self._write_wrapped_rich(text, base_size=size, base_bold=True)

    def paragraph(self, text: str, size: int = 10) -> None:
        self._write_wrapped_rich(text, base_size=size, base_bold=False)

    def rich_line(self, parts: List[Tuple[str, bool]], *, size: int = 10) -> None:
        text = "".join([seg for seg, _ in parts]).strip()
        if not text:
            return

        rebuilt = []
        for seg, is_bold in parts:
            if not seg:
                continue
            if is_bold:
                rebuilt.append(f"**{seg}**")
            else:
                rebuilt.append(seg)
        marked = "".join(rebuilt)

        self._write_wrapped_rich(marked, base_size=size, base_bold=False)

    def bullet(self, text: str, size: int = 10) -> None:
        bullet_x = self.x
        text_x = self.x + 12
        self._ensure_space(1)
        self.c.setFont("Helvetica", size)
        self.c.drawString(bullet_x, self.y, "•")
        self._write_wrapped_rich(text, base_size=size, base_bold=False, x=text_x, hanging_indent=text_x)

    def two_column_bullets(self, items: List[str], size: int = 9) -> None:
        clean = [str(x).strip() for x in items if str(x).strip()]
        if not clean:
            return

        half = math.ceil(len(clean) / 2)
        left_items = clean[:half]
        right_items = clean[half:]

        col_gap = 22
        total_w = self.layout.usable_width
        col_w = (total_w - col_gap) / 2
        left_x = self.x
        right_x = self.x + col_w + col_gap

        max_rows = max(len(left_items), len(right_items))
        for i in range(max_rows):
            self._ensure_space(2)

            start_y = self.y

            left_height = 0.0
            if i < len(left_items):
                left_height = self._draw_bullet_block(
                    left_items[i],
                    x=left_x,
                    width=col_w,
                    size=size,
                )

            right_height = 0.0
            if i < len(right_items):
                right_height = self._draw_bullet_block(
                    right_items[i],
                    x=right_x,
                    width=col_w,
                    size=size,
                    y=start_y,
                )

            used = max(left_height, right_height, self.layout.line_gap * 0.9)
            self.y = start_y - used - 2

    def _draw_bullet_block(self, text: str, *, x: float, width: float, size: int = 9, y: float | None = None) -> float:
        if y is None:
            y = self.y

        items = self._wrap_rich_to_lines(text, width - 12, size, force_bold=False)
        cursor_y = y

        self.c.setFont("Helvetica", size)
        self.c.drawString(x, cursor_y, "•")

        first = True
        for line_items in items:
            text_x = x + 10 if first else x + 10
            self._draw_rich_line_at(line_items, x=text_x, y=cursor_y, size=size, force_bold=False)
            cursor_y -= self.layout.line_gap * 0.82
            first = False

        used_height = max(self.layout.line_gap * 0.82, (len(items)) * self.layout.line_gap * 0.82)
        return used_height

    # ---------- left/right aligned rows ----------
    def left_right_line(
        self,
        left: str,
        right: str,
        *,
        left_font: str = "Helvetica",
        right_font: str = "Helvetica",
        size: int = 10,
    ) -> None:
        left = (left or "").strip()
        right = (right or "").strip()

        self._ensure_space(1)

        right_w = pdfmetrics.stringWidth(right, right_font, size) if right else 0.0
        gap = 10.0
        max_left_w = max(50.0, self.layout.usable_width - right_w - gap)

        left_lines = self._wrap_plain(left, left_font, size, max_left_w) if left else [""]

        self.c.setFont(left_font, size)
        self.c.drawString(self.x, self.y, left_lines[0] if left_lines else "")

        if right:
            rx = self.layout.width - self.layout.right - right_w
            self.c.setFont(right_font, size)
            self.c.drawString(rx, self.y, right)

        self.y -= self.layout.line_gap * 0.95

        for ln in left_lines[1:]:
            self._ensure_space(1)
            self.c.setFont(left_font, size)
            self.c.drawString(self.x, self.y, ln)
            self.y -= self.layout.line_gap * 0.92

    def left_right_rich(
        self,
        left: str,
        right: str,
        *,
        left_bold: bool = True,
        right_bold: bool = False,
        size: int = 10,
    ) -> None:
        left = (left or "").strip()
        right = (right or "").strip()

        self._ensure_space(1)

        right_font = "Helvetica-Bold" if right_bold else "Helvetica"
        right_w = pdfmetrics.stringWidth(right, right_font, size) if right else 0.0
        gap = 10.0
        max_left_w = max(50.0, self.layout.usable_width - right_w - gap)

        left_lines_items = self._wrap_rich_to_lines(left, max_left_w, size, force_bold=left_bold)

        self._draw_rich_line(left_lines_items[0] if left_lines_items else [], x=self.x, size=size, force_bold=left_bold)

        if right:
            rx = self.layout.width - self.layout.right - right_w
            self.c.setFont(right_font, size)
            self.c.drawString(rx, self.y, right)

        self.y -= self.layout.line_gap * 0.95

        for items in left_lines_items[1:]:
            self._ensure_space(1)
            self._draw_rich_line(items, x=self.x, size=size, force_bold=left_bold)
            self.y -= self.layout.line_gap * 0.92

    def bullet_left_right(self, left: str, right: str, *, size: int = 10) -> None:
        left = (left or "").strip()
        right = (right or "").strip()

        bullet_x = self.x
        text_x = self.x + 12

        self._ensure_space(1)
        self.c.setFont("Helvetica", size)
        self.c.drawString(bullet_x, self.y, "•")

        right_w = pdfmetrics.stringWidth(right, "Helvetica", size) if right else 0.0
        gap = 10.0
        max_left_w = max(60.0, (self.layout.width - self.layout.right) - text_x - (right_w + gap if right else 0))

        left_lines = self._wrap_plain(left, "Helvetica", size, max_left_w) if left else [""]

        self.c.setFont("Helvetica", size)
        self.c.drawString(text_x, self.y, left_lines[0] if left_lines else "")

        if right:
            rx = self.layout.width - self.layout.right - right_w
            self.c.drawString(rx, self.y, right)

        self.y -= self.layout.line_gap * 0.95

        for ln in left_lines[1:]:
            self._ensure_space(1)
            self.c.setFont("Helvetica", size)
            self.c.drawString(text_x, self.y, ln)
            self.y -= self.layout.line_gap * 0.9

    # ---------- internal primitives ----------
    def _draw_left_text(self, text: str, font: str, size: int) -> None:
        self.c.setFont(font, size)
        self.c.drawString(self.x, self.y, text)

    def _draw_center_text(self, text: str, font: str, size: int) -> None:
        self.c.setFont(font, size)
        w = pdfmetrics.stringWidth(text, font, size)
        x = (self.layout.width - w) / 2.0
        self.c.drawString(x, self.y, text)

    # ---------- rich text wrapping ----------
    def _split_rich(self, text: str) -> List[Tuple[str, bool]]:
        parts = self._BOLD_RE.split(text or "")
        out: List[Tuple[str, bool]] = []
        for p in parts:
            if p.startswith("**") and p.endswith("**") and len(p) >= 4:
                out.append((p[2:-2], True))
            else:
                out.append((p, False))
        return out

    def _wrap_plain(self, text: str, font: str, size: int, max_w: float) -> List[str]:
        if not text:
            return [""]
        words = re.split(r"\s+", text.strip())
        lines: List[str] = []
        cur: List[str] = []
        cur_w = 0.0
        for w in words:
            piece = w if not cur else (" " + w)
            pw = pdfmetrics.stringWidth(piece, font, size)
            if cur and (cur_w + pw) > max_w:
                lines.append("".join(cur).strip())
                cur = [w]
                cur_w = pdfmetrics.stringWidth(w, font, size)
            else:
                cur.append(piece if cur else w)
                cur_w += pw if cur and piece.startswith(" ") else pdfmetrics.stringWidth(w, font, size)
        if cur:
            lines.append("".join(cur).strip())
        return lines if lines else [""]

    def _wrap_rich_to_lines(self, text: str, max_w: float, size: int, *, force_bold: bool) -> List[List[Tuple[str, bool]]]:
        chunks = self._split_rich(text)
        words: List[Tuple[str, bool]] = []
        for chunk_text, is_bold in chunks:
            for w in re.split(r"(\s+)", chunk_text):
                if w == "":
                    continue
                words.append((w, is_bold))

        def word_width(w: str, bold: bool) -> float:
            font = "Helvetica-Bold" if (force_bold or bold) else "Helvetica"
            return pdfmetrics.stringWidth(w, font, size)

        lines: List[List[Tuple[str, bool]]] = []
        line_items: List[Tuple[str, bool]] = []
        line_w = 0.0

        for w, is_bold in words:
            if not line_items and w.isspace():
                continue

            ww = word_width(w, is_bold)
            if line_items and (line_w + ww) > max_w:
                lines.append(line_items)
                line_items = []
                line_w = 0.0
                if w.isspace():
                    continue

            line_items.append((w, is_bold))
            line_w += ww

        if line_items:
            lines.append(line_items)

        return lines if lines else [[]]

    def _draw_rich_line(self, items: List[Tuple[str, bool]], *, x: float, size: int, force_bold: bool = False) -> None:
        cursor = x
        for txt, is_bold in items:
            bold = force_bold or is_bold
            font = "Helvetica-Bold" if bold else "Helvetica"
            self.c.setFont(font, size)
            self.c.drawString(cursor, self.y, txt)
            cursor += pdfmetrics.stringWidth(txt, font, size)

    def _draw_rich_line_at(self, items: List[Tuple[str, bool]], *, x: float, y: float, size: int, force_bold: bool = False) -> None:
        cursor = x
        for txt, is_bold in items:
            bold = force_bold or is_bold
            font = "Helvetica-Bold" if bold else "Helvetica"
            self.c.setFont(font, size)
            self.c.drawString(cursor, y, txt)
            cursor += pdfmetrics.stringWidth(txt, font, size)

    def _write_wrapped_rich(
        self,
        text: str,
        *,
        base_size: int = 10,
        base_bold: bool = False,
        x: float | None = None,
        hanging_indent: float | None = None,
    ) -> None:
        if x is None:
            x = self.x
        if hanging_indent is None:
            hanging_indent = x

        max_w = (self.layout.width - self.layout.right) - x
        lines_items = self._wrap_rich_to_lines(text, max_w, base_size, force_bold=base_bold)

        first = True
        for items in lines_items:
            self._ensure_space(1)
            self._draw_rich_line(items, x=x if first else hanging_indent, size=base_size, force_bold=base_bold)
            self.y -= self.layout.line_gap * 0.9
            first = False


# ============================================================
# Coercion helpers
# ============================================================
def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _as_list_of_dicts(x: Any) -> List[Dict[str, Any]]:
    if x is None:
        return []
    if isinstance(x, list):
        return [i for i in x if isinstance(i, dict)]
    if isinstance(x, dict):
        return [x]
    return []


def _join_nonempty(parts: List[str], sep: str = " ") -> str:
    out = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    return sep.join(out)


def _join_dates(start: str, end: str) -> str:
    start = (start or "").strip()
    end = (end or "").strip()
    if start and end:
        return f"{start} – {end}"
    return start or end


def _coerce_bullets(bullets: Any) -> List[str]:
    if bullets is None:
        return []
    if isinstance(bullets, list):
        return [str(x).strip() for x in bullets if str(x).strip()]
    if isinstance(bullets, str):
        lines = [ln.strip("• \t").strip() for ln in bullets.splitlines()]
        return [ln for ln in lines if ln]
    return [str(bullets).strip()] if str(bullets).strip() else []


def _strip_md_bold_markers(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", str(text)).strip()


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