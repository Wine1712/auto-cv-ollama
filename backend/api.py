# backend/api.py
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

from backend.cover_service import CoverInputs, generate_cover_letter
from backend.render_cover_docx import render_cover_docx
from backend.render_cover_pdf import render_cover_pdf
from backend.jd_highlight_service import JDHighlightInputs, generate_jd_highlights
from backend.ats_score_service import ATSScoreInputs, score_cv_against_jd
from backend.senior_recruiter_check_service import (
    SeniorRecruiterCheckInputs,
    run_senior_recruiter_check,
)
from backend.easy_read_check_service import EasyReadCheckInputs, run_easy_read_check

from backend.db import (
    init_db,
    find_user,
    save_user,
    verify_user,
    load_profile,
    save_profile,
    save_draft,
    list_drafts,
    load_draft,
)

from backend.auth import (
    hash_password,
    verify_password,
    validate_password,
    generate_verify_token,
    create_token,
    decode_token,
)

from backend import cv_service
from backend.render_docx import render_docx
from backend.render_pdf import render_pdf

from backend.tracker_routes import router as tracker_router
from backend.tracker_service import ensure_tracker_ready

app = FastAPI(title="Auto CV (Ollama)", version="0.3.1")


# =========================
# Startup
# =========================
@app.on_event("startup")
def _startup():
    init_db()
    ensure_tracker_ready()


# =========================
# Request Models
# =========================
class SignupRequest(BaseModel):
    email: str
    confirm_email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SaveProfileRequest(BaseModel):
    profile: Dict[str, Any]


class GenerateCVRequest(BaseModel):
    company: str = ""
    job_title: str = ""
    job_description: str = Field(..., min_length=20)
    model: str = "llama3.1"


class SaveEditedRequest(BaseModel):
    draft_id: str
    edited: Dict[str, Any]


class GenerateCoverRequest(BaseModel):
    draft_id: str
    model: str = "llama3.1"


class SaveCoverEditedRequest(BaseModel):
    draft_id: str
    cover_letter: str


class GenerateJDHighlightsRequest(BaseModel):
    company: str = ""
    job_title: str = ""
    job_description: str = Field(..., min_length=20)
    model: str = "llama3.1"


class ATSScoreRequest(BaseModel):
    draft_id: str
    model: str = "llama3.1"


class RecruiterCheckRequest(BaseModel):
    draft_id: str
    model: str = "llama3.1"


class ReadabilityCheckRequest(BaseModel):
    draft_id: str
    model: str = "llama3.1"


# =========================
# Helpers
# =========================
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename_part(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\w\-\.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:80] if s else ""


def _safe_filename(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"[^\w\-\.]+", "_", s)
    return s[:120] if s else "file"


def _get_email_from_auth(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub") or payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return str(email).strip().lower()


def _exports_dir_for_email(email: str) -> Path:
    base = Path(__file__).resolve().parents[1] / "exports"
    safe = re.sub(r"[^a-z0-9._-]+", "_", email.strip().lower())
    d = base / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _month_year_now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%b_%Y")


def _build_export_filename(*, cv: Dict[str, Any], company: str, job_title: str, ext: str) -> str:
    header = (cv.get("header") or {}) if isinstance(cv.get("header"), dict) else {}
    name = _safe_filename_part(header.get("name") or "Candidate")
    jt = _safe_filename_part(job_title or "CV")
    co = _safe_filename_part(company or "Company")
    my = _safe_filename_part(_month_year_now_utc())

    base = "_".join([p for p in [name, jt, co, my] if p])
    base = _safe_filename(base)
    return f"{base}.{ext}"


def _build_draft_name(*, cv: Dict[str, Any], company: str, job_title: str, version: str = "Ver1.0") -> str:
    header = (cv.get("header") or {}) if isinstance(cv.get("header"), dict) else {}
    name = _safe_filename_part(header.get("name") or "Candidate")
    jt = _safe_filename_part(job_title or "CV")
    co = _safe_filename_part(company or "Company")
    my = _safe_filename_part(_month_year_now_utc())

    base = "_".join([p for p in [name, jt, co, my, version] if p])
    return _safe_filename(base)


# =========================
# Auth Routes
# =========================
@app.post("/auth/signup")
def signup(req: SignupRequest):
    email = req.email.strip().lower()
    confirm = req.confirm_email.strip().lower()

    if email != confirm:
        raise HTTPException(status_code=400, detail="Email and Confirm Email do not match")

    if find_user(email):
        raise HTTPException(status_code=400, detail="Email already registered")

    err = validate_password(req.password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    verify_token = generate_verify_token()
    save_user(email=email, password_hash=hash_password(req.password), verify_token=verify_token)

    verification_link = f"http://127.0.0.1:8000/auth/verify/{verify_token}"
    return {"message": "Account created. Verify your email.", "verify_link": verification_link}


@app.get("/auth/verify/{token}")
def verify(token: str):
    ok = verify_user(token)
    if ok is False:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    return {"message": "Account verified. You can now login."}


@app.post("/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    user = find_user(email)

    if not user:
        raise HTTPException(status_code=401, detail="Wrong email or password")

    if user.get("verified") != "True":
        raise HTTPException(status_code=401, detail="Please verify your email first")

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Wrong email or password")

    token = create_token(email)
    return {"access_token": token, "token_type": "bearer"}


# =========================
# Profile Routes
# =========================
@app.get("/profile")
def get_profile_api(authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    prof = load_profile(email) or {}
    return {"profile": prof}


@app.post("/profile")
def save_profile_api(req: SaveProfileRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    save_profile(email, req.profile)
    return {"ok": True}


# =========================
# Job Description Highlight Routes
# =========================
@app.post("/jd/highlights")
def jd_highlights(req: GenerateJDHighlightsRequest, authorization: Optional[str] = Header(default=None)):
    _get_email_from_auth(authorization)

    highlights = generate_jd_highlights(
        JDHighlightInputs(
            job_description=req.job_description.strip(),
            company=(req.company or "").strip(),
            job_title=(req.job_title or "").strip(),
            model=(req.model or "llama3.1").strip(),
        )
    )
    return {"highlights": highlights}


# =========================
# ATS Score Routes
# =========================
@app.post("/ats/score")
def ats_score(req: ATSScoreRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, req.draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    job_description = (d.get("job_description") or "").strip()
    cv = d.get("cv") or {}

    if not job_description:
        raise HTTPException(status_code=400, detail="Job description missing in draft")

    if not cv:
        raise HTTPException(status_code=400, detail="CV not found in draft")

    result = score_cv_against_jd(
        ATSScoreInputs(
            job_description=job_description,
            cv=cv,
            model=(req.model or "llama3.1").strip(),
        )
    )

    d["ats_score_result"] = result
    meta = d.get("_meta") or {}
    meta["ats_scored_at"] = _utc_now_iso()
    d["_meta"] = meta

    save_draft(email, req.draft_id, d)
    return {"draft_id": req.draft_id, "ats_score": result}


# =========================
# Recruiter Check Routes
# =========================
@app.post("/recruiter/check")
def recruiter_check(req: RecruiterCheckRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, req.draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    job_description = (d.get("job_description") or "").strip()
    cv = d.get("cv") or {}

    if not job_description:
        raise HTTPException(status_code=400, detail="Job description missing in draft")

    if not cv:
        raise HTTPException(status_code=400, detail="CV not found in draft")

    result = run_senior_recruiter_check(
    SeniorRecruiterCheckInputs(
        job_description=job_description,
        cv=cv,
        model=(req.model or "llama3.1").strip(),
    )
)

    d["recruiter_check_result"] = result
    meta = d.get("_meta") or {}
    meta["recruiter_checked_at"] = _utc_now_iso()
    d["_meta"] = meta

    save_draft(email, req.draft_id, d)
    return {"draft_id": req.draft_id, "recruiter_check": result}


# =========================
# Readability Check Routes
# =========================
@app.post("/readability/check")
def readability_check(req: ReadabilityCheckRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, req.draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    cv = d.get("cv") or {}
    if not cv:
        raise HTTPException(status_code=400, detail="CV not found in draft")

    result = run_easy_read_check(
        EasyReadCheckInputs(
            cv=cv,
            model=(req.model or "llama3.1").strip(),
        )
    )

    d["easy_read_result"] = result
    meta = d.get("_meta") or {}
    meta["readability_checked_at"] = _utc_now_iso()
    d["_meta"] = meta

    save_draft(email, req.draft_id, d)
    return {"draft_id": req.draft_id, "easy_read_check": result}


# =========================
# CV Routes
# =========================
@app.get("/cv/drafts")
def cv_list_drafts(authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    items = list_drafts(email) or []
    out: List[Dict[str, Any]] = []
    for it in items:
        meta = it.get("_meta") or {}
        out.append(
            {
                "draft_id": meta.get("draft_id") or it.get("draft_id"),
                "draft_name": it.get("draft_name") or meta.get("draft_name") or meta.get("draft_id") or it.get("draft_id"),
                "created_at": meta.get("created_at") or it.get("created_at"),
                "company": it.get("company", ""),
                "job_title": it.get("job_title", ""),
            }
        )
    return out


@app.get("/cv/drafts/{draft_id}")
def cv_get_draft(draft_id: str, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    d = load_draft(email, draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")
    return d


@app.post("/cv/generate")
def cv_generate(req: GenerateCVRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    profile = load_profile(email) or {}
    if not profile:
        raise HTTPException(status_code=400, detail="Master profile is missing. Please create it first.")

    jd = req.job_description.strip()

    cv = cv_service.generate_targeted_cv(
        cv_service.GenerateInputs(
            profile=profile,
            job_description=jd,
            company=(req.company or "").strip(),
            job_title=(req.job_title or "").strip(),
            model=(req.model or "llama3.1").strip(),
        )
    )

    draft_name = _build_draft_name(
        cv=cv,
        company=(req.company or "").strip(),
        job_title=(req.job_title or "").strip(),
        version="Ver1.0",
    )

    draft_id = str(uuid.uuid4())
    payload = {
        "draft_id": draft_id,
        "draft_name": draft_name,
        "company": (req.company or "").strip(),
        "job_title": (req.job_title or "").strip(),
        "job_description": jd,
        "cv": cv,
        "_meta": {
            "draft_id": draft_id,
            "draft_name": draft_name,
            "created_at": _utc_now_iso(),
            "email": email,
            "model": (req.model or "llama3.1").strip(),
        },
    }
    save_draft(email, draft_id, payload)
    return {"draft_id": draft_id, "draft_name": draft_name, "cv": cv}


@app.post("/cv/save_edited")
def cv_save_edited(req: SaveEditedRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    existing = load_draft(email, req.draft_id) or {}
    if not existing:
        raise HTTPException(status_code=404, detail="Draft not found")

    existing["cv"] = req.edited
    meta = existing.get("_meta") or {}
    meta["updated_at"] = _utc_now_iso()
    existing["_meta"] = meta

    save_draft(email, req.draft_id, existing)
    return {"ok": True}


@app.get("/cv/export/{draft_id}/docx")
def cv_export_docx(draft_id: str, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    d = load_draft(email, draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    cv = d.get("cv") or {}
    company = (d.get("company") or "").strip()
    job_title = (d.get("job_title") or "").strip()

    filename = _build_export_filename(cv=cv, company=company, job_title=job_title, ext="docx")
    out_dir = _exports_dir_for_email(email)
    out_path = out_dir / filename

    render_docx(out_path, cv)
    return {"file_path": str(out_path), "filename": filename}


@app.get("/cv/export/{draft_id}/pdf")
def cv_export_pdf(draft_id: str, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    d = load_draft(email, draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    cv = d.get("cv") or {}
    company = (d.get("company") or "").strip()
    job_title = (d.get("job_title") or "").strip()

    filename = _build_export_filename(cv=cv, company=company, job_title=job_title, ext="pdf")
    out_dir = _exports_dir_for_email(email)
    out_path = out_dir / filename

    render_pdf(out_path, cv)
    return {"file_path": str(out_path), "filename": filename}


# =========================
# Cover Letter Routes
# =========================
@app.post("/cover/generate")
def cover_generate(req: GenerateCoverRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, req.draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    cv = d.get("cv") or {}
    job_description = (d.get("job_description") or "").strip()
    company = (d.get("company") or "").strip()
    job_title = (d.get("job_title") or "").strip()

    if not job_description:
        raise HTTPException(status_code=400, detail="Job description missing in draft")

    cover_letter = generate_cover_letter(
        CoverInputs(
            cv=cv,
            job_description=job_description,
            company=company,
            job_title=job_title,
            model=(req.model or "llama3.1").strip(),
        )
    )

    d["cover_letter"] = cover_letter
    meta = d.get("_meta") or {}
    meta["cover_updated_at"] = _utc_now_iso()
    d["_meta"] = meta

    save_draft(email, req.draft_id, d)
    return {"draft_id": req.draft_id, "cover_letter": cover_letter}


@app.post("/cover/save_edited")
def cover_save_edited(req: SaveCoverEditedRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, req.draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    d["cover_letter"] = (req.cover_letter or "").strip()
    meta = d.get("_meta") or {}
    meta["cover_updated_at"] = _utc_now_iso()
    d["_meta"] = meta

    save_draft(email, req.draft_id, d)
    return {"ok": True}


@app.get("/cover/export/{draft_id}/docx")
def cover_export_docx(draft_id: str, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    cover_letter = (d.get("cover_letter") or "").strip()
    if not cover_letter:
        raise HTTPException(status_code=400, detail="Cover letter not found. Generate it first.")

    cv = d.get("cv") or {}
    company = (d.get("company") or "").strip()
    job_title = (d.get("job_title") or "").strip()

    filename = _build_export_filename(
        cv=cv,
        company=company,
        job_title=f"{job_title}_Cover_Letter",
        ext="docx",
    )
    out_dir = _exports_dir_for_email(email)
    out_path = out_dir / filename

    render_cover_docx(out_path, cv=cv, cover_letter=cover_letter, company=company, job_title=job_title)
    return {"file_path": str(out_path), "filename": filename}


@app.get("/cover/export/{draft_id}/pdf")
def cover_export_pdf(draft_id: str, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    d = load_draft(email, draft_id) or {}
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")

    cover_letter = (d.get("cover_letter") or "").strip()
    if not cover_letter:
        raise HTTPException(status_code=400, detail="Cover letter not found. Generate it first.")

    cv = d.get("cv") or {}
    company = (d.get("company") or "").strip()
    job_title = (d.get("job_title") or "").strip()

    filename = _build_export_filename(
        cv=cv,
        company=company,
        job_title=f"{job_title}_Cover_Letter",
        ext="pdf",
    )
    out_dir = _exports_dir_for_email(email)
    out_path = out_dir / filename

    render_cover_pdf(out_path, cv=cv, cover_letter=cover_letter, company=company, job_title=job_title)
    return {"file_path": str(out_path), "filename": filename}


# =========================
# Tracker Routes (include)
# =========================
app.include_router(tracker_router)