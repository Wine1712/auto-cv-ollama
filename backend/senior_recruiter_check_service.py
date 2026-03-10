# backend/senior_recruiter_check_service.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.ollama_client import ollama_generate


@dataclass(frozen=True)
class SeniorRecruiterCheckInputs:
    job_description: str
    cv: Dict[str, Any]
    model: str = "llama3.1"


def run_senior_recruiter_check(inp: SeniorRecruiterCheckInputs) -> Dict[str, Any]:
    jd = (inp.job_description or "").strip()
    if len(jd) < 20:
        raise ValueError("Job description is too short.")

    cv_text = cv_to_text(inp.cv or {})
    if len(cv_text) < 20:
        raise ValueError("CV text is too short.")

    prompt = f"""
Act as a senior recruiter.

Compare my resume to this job description.

Return ONLY valid JSON with exactly this schema:
{{
  "match_score": 0,
  "top_5_missing_keywords": ["...", "...", "...", "...", "..."],
  "top_strengths": ["...", "...", "..."],
  "main_concerns": ["...", "...", "..."],
  "recruiter_summary": "..."
}}

Rules:
- match_score must be an integer from 0 to 100
- top_5_missing_keywords must contain at most 5 items
- top_strengths should contain 3 to 5 concise items
- main_concerns should contain 3 to 5 concise items
- recruiter_summary should be short, honest, and practical
- Do not invent experience, tools, or qualifications not present in the resume

JOB DESCRIPTION:
\"\"\"{jd}\"\"\"

RESUME:
\"\"\"{cv_text}\"\"\"
""".strip()

    raw = ollama_generate(model=inp.model, prompt=prompt, timeout=240)
    data = _parse_json_from_text(raw)

    if not isinstance(data, dict):
        return {
            "match_score": 0,
            "top_5_missing_keywords": [],
            "top_strengths": [],
            "main_concerns": [],
            "recruiter_summary": "",
        }

    return {
        "match_score": _clip_score(data.get("match_score", 0)),
        "top_5_missing_keywords": _coerce_list(data.get("top_5_missing_keywords"), 5),
        "top_strengths": _coerce_list(data.get("top_strengths"), 5),
        "main_concerns": _coerce_list(data.get("main_concerns"), 5),
        "recruiter_summary": str(data.get("recruiter_summary") or "").strip(),
    }


def cv_to_text(cv: Dict[str, Any]) -> str:
    if not isinstance(cv, dict):
        return ""

    lines: List[str] = []

    header = cv.get("header") if isinstance(cv.get("header"), dict) else {}
    for key in ["name", "title", "email", "phone", "location", "linkedin", "github", "portfolio"]:
        val = str(header.get(key) or "").strip()
        if val:
            lines.append(val)

    for sec in [
        "summary",
        "areas_of_expertise",
        "career_highlights",
        "skills",
        "experience",
        "projects",
        "education",
        "certifications",
        "internships",
    ]:
        val = cv.get(sec)

        if isinstance(val, str) and val.strip():
            lines.append(sec.replace("_", " ").title())
            lines.append(val.strip())

        elif isinstance(val, list):
            lines.append(sec.replace("_", " ").title())
            for item in val:
                if isinstance(item, dict):
                    for _, v in item.items():
                        if isinstance(v, list):
                            lines.extend([str(x).strip() for x in v if str(x).strip()])
                        else:
                            s = str(v).strip()
                            if s:
                                lines.append(s)
                else:
                    s = str(item).strip()
                    if s:
                        lines.append(s)

        elif isinstance(val, dict):
            lines.append(sec.replace("_", " ").title())
            for k, v in val.items():
                if isinstance(v, list):
                    vv = ", ".join([str(x).strip() for x in v if str(x).strip()])
                    if vv:
                        lines.append(f"{k}: {vv}")
                else:
                    s = str(v).strip()
                    if s:
                        lines.append(f"{k}: {s}")

    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def _parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _coerce_list(x: Any, limit: int) -> List[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()][:limit]
    if isinstance(x, str) and x.strip():
        parts = re.split(r"[\n•\-]+", x)
        return [p.strip() for p in parts if p.strip()][:limit]
    return []


def _clip_score(x: Any) -> int:
    try:
        val = int(round(float(x)))
    except Exception:
        val = 0
    return max(0, min(100, val))