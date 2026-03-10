# backend/ats_score_service.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

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

STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "were",
    "will", "with", "you", "your", "our", "we", "their", "they", "this",
    "those", "these", "can", "may", "should", "must", "using", "use",
    "preferred", "required", "desirable", "experience", "years", "year",
    "role", "position", "work", "working", "ability", "strong", "good",
    "knowledge", "skills", "skill", "candidate", "team", "teams"
}

CANONICAL_SKILLS = [
    "python",
    "sql",
    "machine learning",
    "deep learning",
    "nlp",
    "llm",
    "rag",
    "retrieval augmented generation",
    "data pipelines",
    "etl",
    "data engineering",
    "azure",
    "aws",
    "gcp",
    "databricks",
    "spark",
    "pyspark",
    "fastapi",
    "flask",
    "docker",
    "kubernetes",
    "mlops",
    "model deployment",
    "ci/cd",
    "git",
    "github",
    "selenium",
    "playwright",
    "web scraping",
    "api",
    "rest api",
    "pandas",
    "numpy",
    "scikit-learn",
    "xgboost",
    "lightgbm",
    "tensorflow",
    "pytorch",
    "transformers",
    "classification",
    "forecasting",
    "time series",
    "computer vision",
    "information retrieval",
    "vector database",
    "faiss",
    "prompt engineering",
    "automation",
    "openai",
    "azure openai",
    "postgresql",
    "mysql",
    "linux",
]


@dataclass(frozen=True)
class ATSScoreInputs:
    job_description: str
    cv: Dict[str, Any]
    model: str = "llama3.1"


def score_cv_against_jd(inp: ATSScoreInputs) -> Dict[str, Any]:
    jd = clean_text(inp.job_description or "")
    if len(jd) < 20:
        raise ValueError("Job description is too short.")

    cv_text = cv_to_text(inp.cv or {})
    if len(cv_text.strip()) < 20:
        raise ValueError("CV text is too short for ATS scoring.")

    jd_keywords = extract_skills_from_jd(jd)

    matched_keywords, missing_keywords, keyword_match_score = extract_present_keywords_from_cv(
        cv_text=cv_text,
        jd_keywords=jd_keywords,
    )

    formatting_score = formatting_score_from_text(cv_text)

    llm_result = call_llm_for_semantic_analysis(
        job_description=jd,
        cv_text=cv_text,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        model=inp.model,
    )

    semantic_match_score = clip_score(llm_result.get("semantic_match_score", 0))
    experience_match_score = clip_score(llm_result.get("experience_match_score", 0))
    education_match_score = clip_score(llm_result.get("education_match_score", 0))

    overall_score = clip_score(
        0.30 * keyword_match_score +
        0.25 * semantic_match_score +
        0.20 * experience_match_score +
        0.10 * education_match_score +
        0.15 * formatting_score
    )

    strengths = _coerce_str_list(llm_result.get("strengths"), 6)
    weaknesses = _coerce_str_list(llm_result.get("weaknesses"), 6)
    rewrite_suggestions = _coerce_str_list(llm_result.get("rewrite_suggestions"), 10)
    rewritten_summary = str(llm_result.get("rewritten_summary") or "").strip()
    verdict = str(llm_result.get("verdict") or "Moderate Match").strip()

    return {
        "overall_score": overall_score,
        "keyword_match_score": keyword_match_score,
        "semantic_match_score": semantic_match_score,
        "experience_match_score": experience_match_score,
        "education_match_score": education_match_score,
        "formatting_score": formatting_score,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "rewrite_suggestions": rewrite_suggestions,
        "rewritten_summary": rewritten_summary,
        "verdict": verdict,
        "cv_text": cv_text,
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

    summary = str(cv.get("summary") or "").strip()
    if summary:
        lines.append("Professional Summary")
        lines.append(summary)

    for sec in ["areas_of_expertise", "career_highlights"]:
        vals = cv.get(sec)
        if isinstance(vals, list) and vals:
            lines.append(sec.replace("_", " ").title())
            lines.extend([str(v).strip() for v in vals if str(v).strip()])

    skills = cv.get("skills")
    if isinstance(skills, dict):
        lines.append("Skills")
        for cat, items in skills.items():
            if isinstance(items, list) and items:
                lines.append(f"{cat}: {', '.join(str(x).strip() for x in items if str(x).strip())}")
            elif isinstance(items, str) and items.strip():
                lines.append(f"{cat}: {items.strip()}")

    for sec_name in ["experience", "projects", "education", "certifications", "internships"]:
        items = cv.get(sec_name)
        if not isinstance(items, list) or not items:
            continue

        lines.append(sec_name.title())

        for item in items:
            if isinstance(item, dict):
                for _, val in item.items():
                    if isinstance(val, list):
                        lines.extend([str(v).strip() for v in val if str(v).strip()])
                    else:
                        s = str(val).strip()
                        if s:
                            lines.append(s)
            else:
                s = str(item).strip()
                if s:
                    lines.append(s)

    return clean_text("\n".join(lines))


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\+\#\/\-\.\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        key = x.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(x)
    return out


def count_occurrences(text: str, phrase: str) -> int:
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return len(re.findall(pattern, text))


def clip_score(x: float) -> int:
    return max(0, min(100, int(round(x))))


def extract_skills_from_jd(job_description: str) -> List[str]:
    jd = normalize_text(job_description)
    found = []

    for skill in CANONICAL_SKILLS:
        if skill in jd:
            found.append(skill)

    extra_patterns = [
        r"experience with ([a-z0-9\-/\+\#\s,]+?)(?:\.|;|\n|$)",
        r"proficient in ([a-z0-9\-/\+\#\s,]+?)(?:\.|;|\n|$)",
        r"required[:\s]+([a-z0-9\-/\+\#\s,]+?)(?:\.|;|\n|$)",
        r"skills[:\s]+([a-z0-9\-/\+\#\s,]+?)(?:\.|;|\n|$)",
        r"must have[:\s]+([a-z0-9\-/\+\#\s,]+?)(?:\.|;|\n|$)",
    ]

    for pattern in extra_patterns:
        for match in re.findall(pattern, jd, flags=re.IGNORECASE):
            parts = re.split(r",|/| and ", match)
            for p in parts:
                p = p.strip(" .-")
                if len(p) >= 3 and p not in STOPWORDS and len(p.split()) <= 4:
                    found.append(p)

    cleaned = []
    for item in found:
        item = item.strip().lower()
        if item and item not in STOPWORDS and len(item) >= 2:
            cleaned.append(item)

    return unique_keep_order(cleaned)


def extract_present_keywords_from_cv(cv_text: str, jd_keywords: List[str]) -> Tuple[List[str], List[str], int]:
    cv = normalize_text(cv_text)

    matched = []
    missing = []

    for kw in jd_keywords:
        if count_occurrences(cv, kw) > 0:
            matched.append(kw)
        else:
            missing.append(kw)

    if not jd_keywords:
        score = 0
    else:
        base = len(matched) / len(jd_keywords) * 100
        density_bonus = 0.0
        for kw in matched:
            freq = count_occurrences(cv, kw)
            density_bonus += min(freq - 1, 2) * 1.5
        score = min(100, base + density_bonus)

    return matched, missing, clip_score(score)


def formatting_score_from_text(cv_text: str) -> int:
    text = cv_text.strip()
    lower = text.lower()

    score = 75

    standard_sections = [
        "summary",
        "professional summary",
        "skills",
        "experience",
        "work experience",
        "education",
        "projects",
    ]

    found_sections = sum(1 for s in standard_sections if s in lower)
    score += min(found_sections * 4, 16)

    if "|" * 3 in text:
        score -= 5

    if len(re.findall(r"[■◆●★✓✔]", text)) > 5:
        score -= 8

    if len(text.splitlines()) < 5:
        score -= 8

    if len(text) < 300:
        score -= 10

    return clip_score(score)


def call_llm_for_semantic_analysis(
    job_description: str,
    cv_text: str,
    matched_keywords: List[str],
    missing_keywords: List[str],
    model: str,
) -> Dict[str, Any]:
    prompt = f"""
You are an ATS-style resume evaluator.

Your job:
Evaluate the CV against the job description.
Be strict and realistic.
Do not invent missing experience.

Return ONLY valid JSON with exactly this schema:
{{
  "semantic_match_score": 0,
  "experience_match_score": 0,
  "education_match_score": 0,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "rewrite_suggestions": ["..."],
  "rewritten_summary": "...",
  "verdict": "Strong Match"
}}

Rules:
- semantic_match_score: 0-100
  Measure overall relevance of responsibilities, tools, and domain fit.
- experience_match_score: 0-100
  Measure direct experience alignment and impact.
- education_match_score: 0-100
  Measure degree/certification fit.
- strengths: 3 to 6 concise bullet-style strings
- weaknesses: 3 to 6 concise bullet-style strings
- rewrite_suggestions: 5 to 10 concrete suggestions that improve ATS score
- rewritten_summary:
  Write a 3-4 line ATS-friendly professional summary tailored to this job.
  Do not invent tools, certifications, or achievements not found in the CV.
- verdict must be one of:
  "Strong Match", "Moderate Match", "Weak Match"

Known matched keywords:
{json.dumps(matched_keywords, ensure_ascii=False)}

Known missing keywords:
{json.dumps(missing_keywords, ensure_ascii=False)}

JOB DESCRIPTION:
\"\"\"{job_description}\"\"\"

CV:
\"\"\"{cv_text}\"\"\"
""".strip()

    raw_text = ollama_generate(model=model, prompt=prompt, timeout=240)
    parsed = _parse_json_from_text(raw_text)

    if not isinstance(parsed, dict):
        return {
            "semantic_match_score": 0,
            "experience_match_score": 0,
            "education_match_score": 0,
            "strengths": [],
            "weaknesses": [],
            "rewrite_suggestions": [],
            "rewritten_summary": "",
            "verdict": "Moderate Match",
        }

    return parsed


def _parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _coerce_str_list(x: Any, max_items: int) -> List[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()][:max_items]
    if isinstance(x, str) and x.strip():
        parts = re.split(r"[\n•\-]+", x)
        return [p.strip() for p in parts if p.strip()][:max_items]
    return []