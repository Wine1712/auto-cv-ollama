# backend/cv_service.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from backend.ollama_client import ollama_generate


SKILL_CATS = [
    "Programming and Data",
    "Machine Learning and AI",
    "Data Engineering and Cloud",
    "Data Processing",
    "Automation",
    "Tools and Libraries",
    "Soft Skills",
    "Domain Strengths",
]


@dataclass(frozen=True)
class GenerateInputs:
    profile: Dict[str, Any]
    job_description: str
    company: str = ""
    job_title: str = ""
    model: str = "llama3.1"


def generate_targeted_cv(inp: GenerateInputs) -> Dict[str, Any]:
    profile = inp.profile or {}
    jd = (inp.job_description or "").strip()
    if len(jd) < 20:
        raise ValueError("Job description is too short.")

    experiences = _as_list_of_dicts(profile.get("experience"))
    projects = _as_list_of_dicts(profile.get("projects"))
    education = _as_list_of_dicts(profile.get("education"))
    internships = _as_list_of_dicts(profile.get("internships"))
    certifications_raw = profile.get("certifications")

    _ensure_dates_on_items(experiences, keys=("start", "end"), out_key="dates")
    _ensure_dates_on_items(projects, keys=("start", "end"), out_key="dates")
    _ensure_dates_on_items(internships, keys=("start", "end"), out_key="dates")
    _ensure_dates_on_items(education, keys=("start", "end"), out_key="dates")

    certifications = _normalize_certifications(certifications_raw)

    profile = dict(profile)
    profile["experience"] = experiences
    profile["projects"] = projects
    profile["internships"] = internships
    profile["education"] = education
    profile["certifications"] = certifications

    header = _resolve_header(profile, fallback_email=None)

    prompt = _build_prompt(
        profile=profile,
        header=header,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
    )

    text = ollama_generate(model=inp.model, prompt=prompt, timeout=240)
    cv = _parse_json_from_text(text)

    if not isinstance(cv, dict):
        sel_exp = _top_k_by_overlap(experiences, jd, 3)
        sel_proj = _top_k_by_overlap(projects, jd, 3)
        cv = _fallback_cv(
            header=header,
            profile=profile,
            sel_exp=sel_exp,
            sel_proj=sel_proj,
            education=education,
            internships=internships,
            certs=certifications,
        )

    # Tight ATS-friendly normalization
    cv["summary"] = _truncate_words(str(cv.get("summary") or "").strip(), 80)

    cv["areas_of_expertise"] = _coerce_text_list(cv.get("areas_of_expertise"), max_items=5)

    if not cv["areas_of_expertise"]:
        cv["areas_of_expertise"] = _fallback_expertise_from_profile(profile)[:5]


    cv["skills"] = _coerce_skills(cv.get("skills"))
    cv["experience"] = _normalize_experience_list(_as_list_of_dicts(cv.get("experience")))[:3]
    cv["projects"] = _normalize_projects_list(_as_list_of_dicts(cv.get("projects")))[:3]
    cv["certifications"] = _normalize_output_certifications(cv.get("certifications"))[:6]
    cv["internships"] = _normalize_internships_list(_as_list_of_dicts(cv.get("internships")))[:3]
    cv["education"] = _normalize_education_list(_as_list_of_dicts(cv.get("education")))[:4]
    cv["header"] = _merge_header(_as_dict(cv.get("header")), header)

    for cat in SKILL_CATS:
        cv["skills"].setdefault(cat, [])

    return cv


def _build_prompt(*, profile: Dict[str, Any], header: Dict[str, Any], jd: str, company: str, job_title: str) -> str:
    return f"""
You are an expert ATS resume writer for consulting, AI, data, and technology roles.

RETURN ONLY VALID JSON.
No markdown fences.
No commentary.
No explanation text.

HARD RULES:
- The CV must be concise and intended to fit within about 2 pages.
- Use ONLY evidence from the user's master profile.
- Use the job description only to decide relevance, wording emphasis, and prioritization.
- Do NOT invent employers, projects, dates, certifications, degrees, responsibilities, metrics, tools, locations, achievements, or titles.
- Keep dates only from the master profile.
- Select ONLY 2 or 3 most relevant experiences from the master profile.
- Select ONLY 2 or 3 most relevant projects from the master profile.
- Use STAR-style bullet points where possible, but only from true profile evidence.
- IMPORTANT info may use **double-asterisks** in summary and bullets, but only where useful and not excessively.

SUMMARY RULES:
Write a professional summary for the target role using the candidate's real background only.

Requirements:
- Keep it to 3–4 lines only.
- Make it ATS-friendly and recruiter-attractive.
- Align it closely with the key priorities from the job description.
- Highlight leadership, measurable impact, domain relevance, and business value where supported by the master profile.
- Include industry-specific keywords, tools, and technologies from the job description when they are truly supported by the profile.
- Emphasize 3 or 4 strongest relevant capabilities, achievements, or strengths from the profile.
- Do NOT invent achievements, metrics, tools, certifications, or experience.
- Keep wording concise, confident, and tailored to the target role.

AREAS OF EXPERTISE RULES:
- "areas_of_expertise" MUST contain no more than 5 items.
- Choose only the strongest areas relevant to the target job.
- Use only evidence from the master profile.
- Keep each item short and ATS-friendly.

SKILLS RULES:
- Skills MUST be grouped into EXACT categories:
  1) Programming and Data
  2) Machine Learning and AI
  3) Data Engineering and Cloud
  4) Data Processing
  5) Automation
  6) Tools and Libraries
  7) Soft Skills
  8) Domain Strengths

EXPERIENCE BULLETS RULES:
- For each selected experience, write 2 to 4 bullet points only.
- Keep each bullet under 20 words.
- Start each bullet with a strong action verb.
- Focus on achievements, contributions, and business impact rather than generic responsibilities.
- Include measurable impact where supported by the master profile, such as %, scale, time saved, productivity improvement, accuracy improvement, or delivery outcomes.
- Include at least one important keyword, responsibility, tool, or domain point from the job description where relevant.
- Do NOT invent numbers, metrics, achievements, responsibilities, or tools.
- Avoid weak phrases like "helped with", "worked on", or "responsible for" unless absolutely necessary.

EXPERIENCE BULLETS RULES:
- For each selected experience, write 2 to 4 bullet points only.
- Keep each bullet under 20 words.
- Start each bullet with a strong action verb.
- Focus on achievements, contributions, and business impact rather than generic responsibilities.
- Include measurable impact where supported by the master profile, such as %, scale, time saved, productivity improvement, accuracy improvement, or delivery outcomes.
- Include at least one important keyword, responsibility, tool, or domain point from the job description where relevant.
- Do NOT invent numbers, metrics, achievements, responsibilities, or tools.
- Avoid weak phrases like "helped with", "worked on", or "responsible for" unless absolutely necessary.

OUTPUT JSON SCHEMA:
{{
  "header": {{
    "name": "...",
    "title": "...",
    "email": "...",
    "phone": "...",
    "location": "...",
    "linkedin": "...",
    "github": "...",
    "portfolio": "..."
  }},
  "summary": "string around 55-80 words",
  "areas_of_expertise": ["max 5 items"],
  "skills": {{
    "Programming and Data": ["...", "..."],
    "Machine Learning and AI": ["...", "..."],
    "Data Engineering and Cloud": ["...", "..."],
    "Data Processing": ["...", "..."],
    "Automation": ["...", "..."],
    "Tools and Libraries": ["...", "..."],
    "Soft Skills": ["...", "..."],
    "Domain Strengths": ["...", "..."]
  }},
  "experience": [
    {{
      "role": "...",
      "company": "...",
      "dates": "MMM YYYY – MMM YYYY|Present",
      "bullets": ["...", "...", "..."]
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "tech": "...",
      "dates": "MMM YYYY – MMM YYYY|Present",
      "bullets": ["...", "..."]
    }}
  ],
  "education": [
    {{
      "degree": "...",
      "university": "...",
      "city": "...",
      "country": "...",
      "start": "MMM YYYY",
      "end": "MMM YYYY",
      "dates": "MMM YYYY – MMM YYYY",
      "coursework": "...",
      "honors": "..."
    }}
  ],
  "certifications": [
    {{
      "title": "...",
      "issuer": "...",
      "dates": "MMM YYYY – MMM YYYY"
    }}
  ],
  "internships": [
    {{
      "role": "...",
      "company": "...",
      "dates": "MMM YYYY – MMM YYYY|Present",
      "bullets": ["...", "..."]
    }}
  ]
}}

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

MASTER PROFILE JSON:
{json.dumps(profile, ensure_ascii=False)}
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


def _ensure_dates_on_items(items: List[Dict[str, Any]], keys: Tuple[str, str], out_key: str) -> None:
    start_key, end_key = keys
    for it in items:
        s = str(it.get(start_key) or "").strip()
        e = str(it.get(end_key) or "").strip()
        if (s or e) and not str(it.get(out_key) or "").strip():
            it[out_key] = _join_dates(s, e)


def _normalize_certifications(x: Any) -> List[Dict[str, str]]:
    if x is None:
        return []

    out: List[Dict[str, str]] = []

    if isinstance(x, list):
        for it in x:
            if isinstance(it, dict):
                title = str(it.get("title") or it.get("name") or "").strip()
                issuer = str(it.get("issuer") or "").strip()
                dates = str(it.get("dates") or "").strip()
                if not dates:
                    dates = _join_dates(str(it.get("start") or "").strip(), str(it.get("end") or "").strip())

                if title or issuer or dates:
                    out.append(
                        {
                            "title": title,
                            "issuer": issuer,
                            "dates": dates,
                        }
                    )
            elif isinstance(it, str):
                s = it.strip()
                if s:
                    out.append(
                        {
                            "title": s,
                            "issuer": "",
                            "dates": "",
                        }
                    )
    elif isinstance(x, dict):
        return _normalize_certifications([x])
    else:
        s = str(x).strip()
        if s:
            out.append({"title": s, "issuer": "", "dates": ""})

    return out[:50]


def _normalize_output_certifications(x: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []

    if isinstance(x, list):
        for it in x:
            if isinstance(it, dict):
                title = str(it.get("title") or it.get("name") or "").strip()
                issuer = str(it.get("issuer") or "").strip()
                dates = str(it.get("dates") or "").strip()
                if not dates:
                    dates = _join_dates(str(it.get("start") or "").strip(), str(it.get("end") or "").strip())

                if title or issuer or dates:
                    out.append({"title": title, "issuer": issuer, "dates": dates})
            elif isinstance(it, str):
                s = it.strip()
                if s:
                    out.append({"title": s, "issuer": "", "dates": ""})
    elif isinstance(x, dict):
        out = _normalize_output_certifications([x])

    return out


def _normalize_experience_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in items:
        role = str(e.get("role") or "").strip()
        company = str(e.get("company") or "").strip()
        dates = str(e.get("dates") or "").strip()
        if not dates:
            dates = _join_dates(str(e.get("start") or "").strip(), str(e.get("end") or "").strip())

        bullets = _as_list(e.get("bullets"))
        if not bullets and isinstance(e.get("description"), str):
            bullets = _split_text_to_bullets(str(e.get("description") or ""))

        bullets = [str(b).strip() for b in bullets if str(b).strip()][:3]

        if role or company or dates or bullets:
            out.append(
                {
                    "role": role,
                    "company": company,
                    "dates": dates,
                    "bullets": bullets,
                }
            )
    return out


def _normalize_projects_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in items:
        name = str(p.get("name") or "").strip()
        tech = str(p.get("tech") or "").strip()
        dates = str(p.get("dates") or "").strip()
        if not dates:
            dates = _join_dates(str(p.get("start") or "").strip(), str(p.get("end") or "").strip())

        bullets = _as_list(p.get("bullets"))
        if not bullets and isinstance(p.get("description"), str):
            bullets = _split_text_to_bullets(str(p.get("description") or ""))

        bullets = [str(b).strip() for b in bullets if str(b).strip()][:2]

        if name or tech or dates or bullets:
            out.append(
                {
                    "name": name,
                    "tech": tech,
                    "dates": dates,
                    "bullets": bullets,
                }
            )
    return out


def _normalize_internships_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items:
        role = str(it.get("role") or "").strip()
        company = str(it.get("company") or "").strip()
        dates = str(it.get("dates") or "").strip()
        if not dates:
            dates = _join_dates(str(it.get("start") or "").strip(), str(it.get("end") or "").strip())

        bullets = _as_list(it.get("bullets"))
        if not bullets and isinstance(it.get("description"), str):
            bullets = _split_text_to_bullets(str(it.get("description") or ""))

        bullets = [str(b).strip() for b in bullets if str(b).strip()][:3]

        if role or company or dates or bullets:
            out.append(
                {
                    "role": role,
                    "company": company,
                    "dates": dates,
                    "bullets": bullets,
                }
            )
    return out


def _normalize_education_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ed in items:
        degree = str(ed.get("degree") or "").strip()
        university = str(ed.get("university") or "").strip()
        city = str(ed.get("city") or "").strip()
        country = str(ed.get("country") or "").strip()
        start = str(ed.get("start") or "").strip()
        end = str(ed.get("end") or "").strip()
        dates = str(ed.get("dates") or "").strip() or _join_dates(start, end)
        coursework = str(ed.get("coursework") or "").strip()
        honors = str(ed.get("honors") or "").strip()

        if degree or university or city or country or start or end or coursework or honors:
            out.append(
                {
                    "degree": degree,
                    "university": university,
                    "city": city,
                    "country": country,
                    "start": start,
                    "end": end,
                    "dates": dates,
                    "coursework": coursework,
                    "honors": honors,
                }
            )
    return out


def _fallback_cv(
    header: Dict[str, Any],
    profile: Dict[str, Any],
    sel_exp: List[Dict[str, Any]],
    sel_proj: List[Dict[str, Any]],
    education: List[Dict[str, Any]],
    internships: List[Dict[str, Any]],
    certs: List[Dict[str, str]],
) -> Dict[str, Any]:
    return {
        "header": header,
        "summary": "Targeted candidate with relevant experience aligned to the role and demonstrated strengths across key responsibilities from the master profile.",
        "areas_of_expertise": _fallback_expertise_from_profile(profile)[:5],
        "skills": {cat: [] for cat in SKILL_CATS},
        "experience": _normalize_experience_list(sel_exp[:3]),
        "projects": _normalize_projects_list(sel_proj[:3]),
        "certifications": certs[:6],
        "internships": _normalize_internships_list(internships[:3]),
        "education": _normalize_education_list(education[:4]),
    }


def _top_k_by_overlap(items: List[Dict[str, Any]], jd: str, k: int) -> List[Dict[str, Any]]:
    jd_tokens = set(re.findall(r"[a-zA-Z]{3,}", jd.lower()))
    scored: List[Tuple[int, Dict[str, Any]]] = []

    for it in items:
        blob = json.dumps(it, ensure_ascii=False).lower()
        it_tokens = set(re.findall(r"[a-zA-Z]{3,}", blob))
        score = len(jd_tokens & it_tokens)
        scored.append((score, it))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:k]]


def _truncate_words(text: str, max_words: int) -> str:
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip() + "…"


def _resolve_header(profile: Dict[str, Any], fallback_email: Optional[str]) -> Dict[str, Any]:
    h = {}
    if isinstance(profile.get("header"), dict):
        h = profile["header"]
    elif isinstance(profile.get("base"), dict):
        h = profile["base"]

    return {
        "name": str(h.get("name") or profile.get("name") or "").strip(),
        "title": str(h.get("title") or profile.get("title") or "").strip(),
        "email": str(h.get("email") or profile.get("email") or fallback_email or "").strip(),
        "phone": str(h.get("phone") or profile.get("phone") or "").strip(),
        "location": str(h.get("location") or profile.get("location") or "").strip(),
        "linkedin": str(h.get("linkedin") or profile.get("linkedin") or "").strip(),
        "github": str(h.get("github") or profile.get("github") or "").strip(),
        "portfolio": str(h.get("portfolio") or "").strip(),
    }


def _merge_header(generated: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": str(generated.get("name") or fallback.get("name") or "").strip(),
        "title": str(generated.get("title") or fallback.get("title") or "").strip(),
        "email": str(generated.get("email") or fallback.get("email") or "").strip(),
        "phone": str(generated.get("phone") or fallback.get("phone") or "").strip(),
        "location": str(generated.get("location") or fallback.get("location") or "").strip(),
        "linkedin": str(generated.get("linkedin") or fallback.get("linkedin") or "").strip(),
        "github": str(generated.get("github") or fallback.get("github") or "").strip(),
        "portfolio": str(generated.get("portfolio") or fallback.get("portfolio") or "").strip(),
    }


def _coerce_skills(skills: Any) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {cat: [] for cat in SKILL_CATS}
    if isinstance(skills, dict):
        for cat in SKILL_CATS:
            v = skills.get(cat)
            if isinstance(v, list):
                out[cat] = [str(x).strip() for x in v if str(x).strip()]
            elif isinstance(v, str) and v.strip():
                out[cat] = [v.strip()]
    return out


def _coerce_text_list(x: Any, max_items: int = 8) -> List[str]:
    out: List[str] = []
    if isinstance(x, list):
        out = [str(i).strip() for i in x if str(i).strip()]
    elif isinstance(x, str) and x.strip():
        parts = re.split(r"[\n•\-]+", x)
        out = [p.strip() for p in parts if p.strip()]
    return out[:max_items]


def _fallback_expertise_from_profile(profile: Dict[str, Any]) -> List[str]:
    expertise = profile.get("expertise", "")
    if isinstance(expertise, str) and expertise.strip():
        items = [x.strip() for x in re.split(r"[,\n]+", expertise) if x.strip()]
        return items[:5]
    return []


def _fallback_highlights_from_profile(profile: Dict[str, Any]) -> List[str]:
    highlights = profile.get("highlights", "")
    if isinstance(highlights, str) and highlights.strip():
        items = [x.strip("• ").strip() for x in re.split(r"[\n]+", highlights) if x.strip()]
        return items[:6]
    return []


def _split_text_to_bullets(text: str) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    lines = [ln.strip("• \t").strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    if lines:
        return lines
    return [text.strip()]


def _join_dates(start: str, end: str) -> str:
    start = (start or "").strip()
    end = (end or "").strip()
    if start and end:
        return f"{start} – {end}"
    return start or end


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