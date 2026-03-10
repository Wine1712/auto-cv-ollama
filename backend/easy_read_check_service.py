# backend/easy_read_check_service.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.ollama_client import ollama_generate


@dataclass(frozen=True)
class EasyReadCheckInputs:
    cv: Dict[str, Any]
    model: str = "llama3.1"


def run_easy_read_check(inp: EasyReadCheckInputs) -> Dict[str, Any]:
    cv_text = cv_to_text(inp.cv or {})
    if len(cv_text) < 20:
        raise ValueError("CV text is too short.")

    prompt = f"""
Now act as an application tracking system filter.

Scan my updated resume and tell me which sections a bot would struggle to read.

Return ONLY valid JSON with exactly this schema:
{{
  "easy_to_read_score": 0,
  "sections_bot_would_struggle": ["...", "..."],
  "formatting_issues": ["...", "..."],
  "ats_readability_fixes": ["...", "..."],
  "overall_readability_summary": "..."
}}

Rules:
- easy_to_read_score must be an integer from 0 to 100
- sections_bot_would_struggle should contain section names or short phrases
- formatting_issues should be specific and practical
- ats_readability_fixes should be concrete improvements
- overall_readability_summary should be short and direct
- Focus on ATS readability, structure, parsing clarity, and section naming
- Do not invent missing sections unless there is evidence they are unclear or absent

UPDATED RESUME:
\"\"\"{cv_text}\"\"\"
""".strip()

    raw = ollama_generate(model=inp.model, prompt=prompt, timeout=240)
    data = _parse_json_from_text(raw)

    if not isinstance(data, dict):
        return {
            "easy_to_read_score": 0,
            "sections_bot_would_struggle": [],
            "formatting_issues": [],
            "ats_readability_fixes": [],
            "overall_readability_summary": "",
        }

    return {
        "easy_to_read_score": _clip_score(data.get("easy_to_read_score", 0)),
        "sections_bot_would_struggle": _coerce_list(data.get("sections_bot_would_struggle"), 8),
        "formatting_issues": _coerce_list(data.get("formatting_issues"), 10),
        "ats_readability_fixes": _coerce_list(data.get("ats_readability_fixes"), 10),
        "overall_readability_summary": str(data.get("overall_readability_summary") or "").strip(),
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