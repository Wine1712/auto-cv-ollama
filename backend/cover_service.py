# backend/cover_service.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from backend.ollama_client import ollama_generate


@dataclass(frozen=True)
class CoverInputs:
    cv: Dict[str, Any]
    job_description: str
    company: str = ""
    job_title: str = ""
    model: str = "llama3.1"


def generate_cover_letter(inp: CoverInputs) -> str:
    cv = inp.cv or {}
    jd = (inp.job_description or "").strip()
    if len(jd) < 20:
        raise ValueError("Job description is too short.")

    prompt = _build_prompt(
        cv=cv,
        jd=jd,
        company=(inp.company or "").strip(),
        job_title=(inp.job_title or "").strip(),
    )

    text = ollama_generate(model=inp.model, prompt=prompt, timeout=240)
    return _clean_cover_text(text)


def _build_prompt(*, cv: Dict[str, Any], jd: str, company: str, job_title: str) -> str:
    header = (cv.get("header") or {}) if isinstance(cv.get("header"), dict) else {}
    name = (header.get("name") or "").strip() or "Candidate"

    greeting = "Dear Hiring Manager,"
    if company:
        greeting = f"Dear {company} Hiring Manager,"

    return f"""
You are an expert Australian cover letter writer.

WRITE A 1-PAGE COVER LETTER (about 250–350 words). No markdown headings. No bullet lists unless necessary.

HARD RULES:
- Use ONLY evidence from the CV content below. Do NOT invent employers, degrees, dates, metrics, tools, or achievements.
- You MAY add **bold** using **double-asterisks** for 3–6 key phrases ONLY.
- Tone: professional, confident, clear, not fluffy.
- Structure:
  1) Greeting line
  2) Paragraph 1: interest + role fit + what you bring
  3) Paragraph 2: 2–3 strongest achievements aligned to JD
  4) Paragraph 3: alignment to responsibilities + collaboration/communication
  5) Closing: availability + thanks + sign-off ("Kind regards, {name}")

OUTPUT:
Return only the cover letter text.

Greeting to use:
{greeting}

JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

TARGETED CV JSON (use as evidence):
{json.dumps(cv, ensure_ascii=False)}
""".strip()


def _clean_cover_text(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    return s.strip("`").strip()