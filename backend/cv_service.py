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

    # Select only the most relevant records first
    sel_exp = _top_k_by_overlap(experiences, jd, 3)
    sel_proj = _top_k_by_overlap(projects, jd, 3)

    # Generate section by section
    summary = _generate_summary(
        profile=profile,
        header=header,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        selected_experience=sel_exp,
        selected_projects=sel_proj,
        model=inp.model,
    )

    generated_education = _generate_education(
        education=education,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        model=inp.model,
    )

    generated_certifications = _generate_certifications(
        certifications=certifications,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        model=inp.model,
    )

    generated_internships = _generate_internships(
        internships=internships,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        model=inp.model,
    )

    areas_of_expertise = _generate_expertise(
        profile=profile,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        selected_experience=sel_exp,
        selected_projects=sel_proj,
        model=inp.model,
    )

    skills = _generate_skills(
        profile=profile,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        model=inp.model,
    )

    generated_experience = _generate_experience(
        selected_experience=sel_exp,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        model=inp.model,
    )

    generated_projects = _generate_projects(
        selected_projects=sel_proj,
        jd=jd,
        company=inp.company,
        job_title=inp.job_title,
        model=inp.model,
    )

    # Final assembled CV
    cv = {
        "header": header,
        "summary": summary,
        "areas_of_expertise": areas_of_expertise,
        "skills": skills,
        "experience": generated_experience,
        "projects": generated_projects,
        "education": generated_education,
        "certifications": generated_certifications,
        "internships": generated_internships,
    }

    # Final normalization / safeguards
    cv["summary"] = _truncate_words(str(cv.get("summary") or "").strip(), 90)

    cv["areas_of_expertise"] = _coerce_text_list(
        cv.get("areas_of_expertise"),
        max_items=5,
    )
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

def _generate_summary(
    *,
    profile: Dict[str, Any],
    header: Dict[str, Any],
    jd: str,
    company: str,
    job_title: str,
    selected_experience: List[Dict[str, Any]],
    selected_projects: List[Dict[str, Any]],
    model: str,
) -> str:
    prompt = f"""
You are an expert ATS resume writer.

Task:
Write only the professional summary section for a CV.

Strict rules:
- Return plain text only.
- Do not return JSON.
- Do not return headings.
- Do not return bullet points.
- Do not return commentary or explanation.
- Keep it to 3-4 lines.
- Keep it concise, modern, ATS-friendly, and recruiter-friendly.
- Highlight the candidate's strongest and most relevant achievements.
- Include measurable impact only if clearly supported by the profile.
- Include important technical keywords from the job description only when supported by the profile.
- Avoid generic HR phrases such as "hardworking", "team player", "results-driven professional", or "seeking an opportunity".
- Focus on the target role, strongest relevant experience, technical depth, and business value.
- Use only true evidence from the profile.
- Do not invent achievements, tools, metrics, domains, or responsibilities.

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

HEADER:
{json.dumps(header, ensure_ascii=False)}

SELECTED EXPERIENCE:
{json.dumps(selected_experience, ensure_ascii=False)}

SELECTED PROJECTS:
{json.dumps(selected_projects, ensure_ascii=False)}

MASTER PROFILE:
{json.dumps(profile, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=180)
    summary = _parse_text_response(text)

    if not summary:
        fallback_title = str(header.get("title") or job_title or "AI-focused candidate").strip()
        return (
            f"{fallback_title} with hands-on experience in machine learning, automation, "
            f"and data-driven solution development. Brings relevant project and technical "
            f"experience aligned to the target role, with strengths in applied AI, data processing, "
            f"and practical business-focused delivery."
        )

    return summary

def _generate_expertise(
    *,
    profile: Dict[str, Any],
    jd: str,
    company: str,
    job_title: str,
    selected_experience: List[Dict[str, Any]],
    selected_projects: List[Dict[str, Any]],
    model: str,
) -> List[str]:
    prompt = f"""
You are an expert ATS resume writer.

Return ONLY a valid JSON array.

Task:
Select the 3 to 5 strongest areas of expertise for this candidate based on the target job.

Rules:
- Return only a JSON list.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Each item must be short, ATS-friendly, and job-relevant.
- Use only evidence from the master profile.
- Do not invent skills, tools, or domains.
- Prioritize the strongest areas most relevant to the target role.

Example:
["Machine Learning", "Data Pipelines", "LLM Applications", "Automation", "Compliance Monitoring"]

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

SELECTED EXPERIENCE:
{json.dumps(selected_experience, ensure_ascii=False)}

SELECTED PROJECTS:
{json.dumps(selected_projects, ensure_ascii=False)}

MASTER PROFILE:
{json.dumps(profile, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=180)
    items = _parse_json_list_from_text(text)
    items = _coerce_text_list(items, max_items=5)

    if not items:
        return _fallback_expertise_from_profile(profile)[:5]

    return items

def _generate_education(
    *,
    education: List[Dict[str, Any]],
    jd: str,
    company: str,
    job_title: str,
    model: str,
) -> List[Dict[str, Any]]:
    if not education:
        return []

    prompt = f"""
You are an expert ATS resume writer.

Return ONLY valid JSON.

Task:
Rewrite the education section for a CV.

Rules:
- Return only a JSON array.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Preserve degree, university, start, end, and dates from the input.
- Keep entries concise and ATS-friendly.
- Do not invent degrees, universities, dates, honors, coursework, city, or country.

Required format:
[
  {{
    "degree": "...",
    "university": "...",
    "city": "...",
    "country": "...",
    "start": "...",
    "end": "...",
    "dates": "...",
    "coursework": "...",
    "honors": "..."
  }}
]

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

EDUCATION INPUT:
{json.dumps(education, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=180)
    items = _parse_json_list_from_text(text)
    items = _normalize_education_list(_as_list_of_dicts(items))[:4]

    if not items:
        return _normalize_education_list(education)[:4]

    return items

def _generate_certifications(
    *,
    certifications: List[Dict[str, Any]],
    jd: str,
    company: str,
    job_title: str,
    model: str,
) -> List[Dict[str, str]]:
    if not certifications:
        return []

    prompt = f"""
You are an expert ATS resume writer.

Return ONLY valid JSON.

Task:
Rewrite the certifications section for a CV.

Rules:
- Return only a JSON array.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Preserve title, issuer, start, end, and dates from the input.
- Keep entries concise and ATS-friendly.
- Do not invent certification names, issuers, or dates.

Required format:
[
  {{
    "title": "...",
    "issuer": "...",
    "start": "...",
    "end": "...",
    "dates": "..."
  }}
]

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

CERTIFICATIONS INPUT:
{json.dumps(certifications, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=180)
    items = _parse_json_list_from_text(text)
    items = _normalize_output_certifications(items)[:6]

    if not items:
        return _normalize_output_certifications(certifications)[:6]

    return items

def _generate_internships(
    *,
    internships: List[Dict[str, Any]],
    jd: str,
    company: str,
    job_title: str,
    model: str,
) -> List[Dict[str, Any]]:
    if not internships:
        return []

    prompt = f"""
You are an expert ATS resume writer.

Return ONLY valid JSON.

Task:
Rewrite the internship entries for a CV.

Rules:
- Return only a JSON array.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Preserve role, company, start, end, and dates from the input.
- Write 1 to 3 bullet points per internship.
- Keep each bullet concise and achievement-focused.
- Include relevant keywords only when supported by the input.
- Do not invent employers, dates, tools, metrics, or achievements.

Required format:
[
  {{
    "role": "...",
    "company": "...",
    "start": "...",
    "end": "...",
    "dates": "...",
    "bullets": ["...", "..."]
  }}
]

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

INTERNSHIPS INPUT:
{json.dumps(internships, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=180)
    items = _parse_json_list_from_text(text)
    items = _normalize_internships_list(_as_list_of_dicts(items))[:3]

    if not items:
        return _normalize_internships_list(internships)[:3]

    return items

def _generate_skills(
    *,
    profile: Dict[str, Any],
    jd: str,
    company: str,
    job_title: str,
    model: str,
) -> Dict[str, List[str]]:
    prompt = f"""
You are an expert ATS resume writer.

Return ONLY valid JSON.

Task:
Group the candidate's relevant skills into the exact categories below.

Rules:
- Return only a JSON object.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Use only evidence from the master profile.
- Use the job description only for prioritization.
- Do not invent skills.

Required categories:
- Programming and Data
- Machine Learning and AI
- Data Engineering and Cloud
- Data Processing
- Automation
- Tools and Libraries
- Soft Skills
- Domain Strengths

Example format:
{{
  "Programming and Data": ["Python", "SQL"],
  "Machine Learning and AI": ["XGBoost", "PyTorch"],
  "Data Engineering and Cloud": ["Azure", "Databricks"],
  "Data Processing": ["ETL", "Data Cleaning"],
  "Automation": ["Web Scraping", "Workflow Automation"],
  "Tools and Libraries": ["Pandas", "Scikit-learn"],
  "Soft Skills": ["Communication", "Problem Solving"],
  "Domain Strengths": ["Compliance Monitoring", "AI Systems"]
}}

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

MASTER PROFILE:
{json.dumps(profile, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=180)
    obj = _parse_json_dict_from_text(text)
    skills = _coerce_skills(obj)

    # fallback if model returns empty
    if not any(skills.values()):
        profile_skills = profile.get("skills", {})
        if isinstance(profile_skills, dict):
            return _coerce_skills(profile_skills)

    return skills

def _generate_experience(
    *,
    selected_experience: List[Dict[str, Any]],
    jd: str,
    company: str,
    job_title: str,
    model: str,
) -> List[Dict[str, Any]]:
    if not selected_experience:
        return []

    prompt = f"""
You are an expert ATS resume writer.

Return ONLY valid JSON.

Task:
Rewrite the selected work experience entries for a CV.

Rules:
- Return only a JSON array.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Preserve role, company, start, end, and dates from the input.
- Write 2 to 4 bullet points per experience.
- Keep each bullet under 20 words.
- Start each bullet with a strong action verb.
- Focus on measurable impact, achievements, and business value where supported.
- Include job-relevant keywords when supported by the source data.
- Do not invent metrics, tools, achievements, dates, employers, or responsibilities.

Required format:
[
  {{
    "role": "...",
    "company": "...",
    "start": "...",
    "end": "...",
    "dates": "...",
    "bullets": ["...", "...", "..."]
  }}
]

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

SELECTED EXPERIENCE INPUT:
{json.dumps(selected_experience, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=240)
    items = _parse_json_list_from_text(text)
    items = _normalize_experience_list(_as_list_of_dicts(items))[:3]

    if not items:
        return _normalize_experience_list(selected_experience)[:3]

    return items

def _generate_projects(
    *,
    selected_projects: List[Dict[str, Any]],
    jd: str,
    company: str,
    job_title: str,
    model: str,
) -> List[Dict[str, Any]]:
    if not selected_projects:
        return []

    prompt = f"""
You are an expert ATS resume writer.

Return ONLY valid JSON.

Task:
Rewrite the selected project entries for a CV.

Rules:
- Return only a JSON array.
- No explanation.
- No markdown.
- No text before or after the JSON.
- Preserve project name, technologies, start, end, and dates from the input.
- Write 1 to 3 bullet points per project.
- Keep each bullet concise and achievement-focused.
- Include job-relevant keywords when supported by the source data.
- Do not invent tools, metrics, dates, or achievements.

Required format:
[
  {{
    "name": "...",
    "tech": "...",
    "start": "...",
    "end": "...",
    "dates": "...",
    "bullets": ["...", "..."]
  }}
]

TARGET JOB:
Company: {company}
Title: {job_title}
Description:
{jd}

SELECTED PROJECTS INPUT:
{json.dumps(selected_projects, ensure_ascii=False)}
""".strip()

    text = ollama_generate(model=model, prompt=prompt, timeout=240)
    items = _parse_json_list_from_text(text)
    items = _normalize_projects_list(_as_list_of_dicts(items))[:3]

    if not items:
        return _normalize_projects_list(selected_projects)[:3]

    return items

def _parse_json_dict_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    text = text.strip()

    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return {}

    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}
    
def _parse_json_list_from_text(text: str) -> List[Any]:
    if not text:
        return []

    text = text.strip()

    try:
        obj = json.loads(text)
        return obj if isinstance(obj, list) else []
    except Exception:
        pass

    m = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not m:
        return []

    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, list) else []
    except Exception:
        return []
    
def _parse_text_response(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


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

                start = str(it.get("start") or "").strip()
                end = str(it.get("end") or "").strip()

                dates = str(it.get("dates") or "").strip()
                if not dates:
                    dates = _join_dates(start, end)

                if title or issuer or start or end or dates:
                    out.append(
                        {
                            "title": title,
                            "issuer": issuer,
                            "start": start,
                            "end": end,
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
                            "start": "",
                            "end": "",
                            "dates": "",
                        }
                    )

    elif isinstance(x, dict):
        return _normalize_certifications([x])

    else:
        s = str(x).strip()
        if s:
            out.append(
                {
                    "title": s,
                    "issuer": "",
                    "start": "",
                    "end": "",
                    "dates": "",
                }
            )

    return out[:50]

def _normalize_output_certifications(x: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []

    if isinstance(x, list):
        for it in x:
            if isinstance(it, dict):
                title = str(it.get("title") or it.get("name") or "").strip()
                issuer = str(it.get("issuer") or "").strip()

                start = str(it.get("start") or "").strip()
                end = str(it.get("end") or "").strip()

                dates = str(it.get("dates") or "").strip()
                if not dates:
                    dates = _join_dates(start, end)

                if title or issuer or start or end or dates:
                    out.append(
                        {
                            "title": title,
                            "issuer": issuer,
                            "start": start,
                            "end": end,
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
                            "start": "",
                            "end": "",
                            "dates": "",
                        }
                    )

    elif isinstance(x, dict):
        out = _normalize_output_certifications([x])

    return out

def _normalize_experience_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in items:
        role = str(e.get("role") or "").strip()
        company = str(e.get("company") or "").strip()

        start = str(e.get("start") or "").strip()
        end = str(e.get("end") or "").strip()

        dates = str(e.get("dates") or "").strip()
        if not dates:
            dates = _join_dates(start, end)

        bullets = _as_list(e.get("bullets"))
        if not bullets and isinstance(e.get("description"), str):
            bullets = _split_text_to_bullets(str(e.get("description") or ""))

        bullets = [str(b).strip() for b in bullets if str(b).strip()][:3]

        if role or company or start or end or dates or bullets:
            out.append(
                {
                    "role": role,
                    "company": company,
                    "start": start,
                    "end": end,
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

        start = str(p.get("start") or "").strip()
        end = str(p.get("end") or "").strip()

        dates = str(p.get("dates") or "").strip()
        if not dates:
            dates = _join_dates(start, end)

        bullets = _as_list(p.get("bullets"))
        if not bullets and isinstance(p.get("description"), str):
            bullets = _split_text_to_bullets(str(p.get("description") or ""))

        bullets = [str(b).strip() for b in bullets if str(b).strip()][:2]

        if name or tech or start or end or dates or bullets:
            out.append(
                {
                    "name": name,
                    "tech": tech,
                    "start": start,
                    "end": end,
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

        start = str(it.get("start") or "").strip()
        end = str(it.get("end") or "").strip()

        dates = str(it.get("dates") or "").strip()
        if not dates:
            dates = _join_dates(start, end)

        bullets = _as_list(it.get("bullets"))
        if not bullets and isinstance(it.get("description"), str):
            bullets = _split_text_to_bullets(str(it.get("description") or ""))

        bullets = [str(b).strip() for b in bullets if str(b).strip()][:3]

        if role or company or start or end or dates or bullets:
            out.append(
                {
                    "role": role,
                    "company": company,
                    "start": start,
                    "end": end,
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