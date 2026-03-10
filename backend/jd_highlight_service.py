# backend/jd_highlight_service.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.ollama_client import ollama_generate


@dataclass(frozen=True)
class JDHighlightInputs:
    job_description: str
    company: str = ""
    job_title: str = ""
    model: str = "llama3.1"


def generate_jd_highlights(inp: JDHighlightInputs) -> Dict[str, Any]:
    jd = (inp.job_description or "").strip()
    if len(jd) < 20:
        raise ValueError("Job description is too short.")

    prompt = _build_prompt(
        jd=jd,
        company=(inp.company or "").strip(),
        job_title=(inp.job_title or "").strip(),
    )

    text = ollama_generate(model=inp.model, prompt=prompt, timeout=180)
    parsed = _parse_json_from_text(text)

    if not isinstance(parsed, dict):
        return _fallback_jd_highlights(jd)

    return _normalize_jd_highlights(parsed, jd)


def _build_prompt(*, jd: str, company: str, job_title: str) -> str:
    return f"""
You are an expert hiring analyst and ATS keyword extractor.

RETURN ONLY VALID JSON.
No markdown.
No explanation.
No extra text.

TASK:
Read the job description and extract the most important hiring signals.

RULES:
- Use only the job description.
- Do not invent missing information.
- Keep lists concise and useful.
- required_skills = core skills the candidate must show
- tools_and_technologies = software, frameworks, platforms, programming languages, cloud tools, analytics tools, libraries, systems
- responsibilities = main duties of the role
- industry_domain = business, industry, or functional context
- hidden_keywords_soft_skills = implied ATS soft skills like communication, stakeholder management, teamwork, adaptability, leadership, ownership, problem solving, collaboration
- level_of_role should describe the likely seniority of the role based on the JD

OUTPUT JSON SCHEMA:
{{
  "level_of_role": "string",
  "required_skills": ["...", "..."],
  "tools_and_technologies": ["...", "..."],
  "responsibilities": ["...", "..."],
  "industry_domain": ["...", "..."],
  "hidden_keywords_soft_skills": ["...", "..."]
}}

JOB:
Company: {company}
Title: {job_title}
Description:
{jd}
""".strip()


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


def _coerce_list(x: Any, max_items: int = 10) -> List[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()][:max_items]

    if isinstance(x, str) and x.strip():
        parts = re.split(r"[\n,•;]+", x)
        return [p.strip(" -").strip() for p in parts if p.strip(" -").strip()][:max_items]

    return []


def _normalize_jd_highlights(d: Dict[str, Any], jd: str) -> Dict[str, Any]:
    out = {
        "level_of_role": str(d.get("level_of_role") or "").strip(),
        "required_skills": _coerce_list(d.get("required_skills"), max_items=10),
        "tools_and_technologies": _coerce_list(d.get("tools_and_technologies"), max_items=10),
        "responsibilities": _coerce_list(d.get("responsibilities"), max_items=10),
        "industry_domain": _coerce_list(d.get("industry_domain"), max_items=6),
        "hidden_keywords_soft_skills": _coerce_list(d.get("hidden_keywords_soft_skills"), max_items=10),
    }

    if not out["level_of_role"]:
        out["level_of_role"] = _infer_role_level(jd)

    if not out["industry_domain"]:
        out["industry_domain"] = _infer_industry_domain(jd)

    return out


def _fallback_jd_highlights(jd: str) -> Dict[str, Any]:
    return {
        "level_of_role": _infer_role_level(jd),
        "required_skills": [],
        "tools_and_technologies": [],
        "responsibilities": [],
        "industry_domain": _infer_industry_domain(jd),
        "hidden_keywords_soft_skills": [],
    }


def _infer_role_level(jd: str) -> str:
    s = jd.lower()

    if any(k in s for k in ["principal", "head of", "director", "lead", "senior manager", "staff engineer"]):
        return "Senior / Lead level"

    if any(k in s for k in ["senior", "manager", "team lead", "lead engineer", "5+ years", "6+ years", "7+ years"]):
        return "Senior level"

    if any(k in s for k in ["mid-level", "intermediate", "3+ years", "4+ years"]):
        return "Mid-level"

    if any(k in s for k in ["junior", "graduate", "entry level", "entry-level", "intern", "1+ years", "2+ years"]):
        return "Junior / Entry level"

    return "Not clearly specified"


def _infer_industry_domain(jd: str) -> List[str]:
    s = jd.lower()
    domains: List[str] = []

    domain_map = {
        "Finance": ["finance", "financial", "bank", "banking", "fintech", "wealth", "lending", "insurance"],
        "Healthcare": ["health", "healthcare", "medical", "hospital", "clinical", "patient"],
        "Education": ["education", "university", "school", "teaching", "learning"],
        "Government": ["government", "public sector", "department", "regulatory", "policy"],
        "Retail": ["retail", "ecommerce", "e-commerce", "consumer", "shopping"],
        "Manufacturing": ["manufacturing", "factory", "production", "industrial", "supply chain"],
        "Technology": ["software", "saas", "platform", "technology", "ai", "data", "digital"],
        "Consulting": ["consulting", "advisory", "client-facing", "client facing"],
        "Energy": ["energy", "electric", "utilities", "power", "electrical"],
        "Telecommunications": ["telecom", "telecommunications", "network", "carrier"],
        "Marketing": ["marketing", "campaign", "brand", "advertising", "seo"],
        "HR / Recruitment": ["recruitment", "talent", "human resources", "hr"],
    }

    for label, keywords in domain_map.items():
        if any(k in s for k in keywords):
            domains.append(label)

    return domains[:6]