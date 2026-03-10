# services/api_client.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def _headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(path: str, token: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=_headers(token), params=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text}")
    return r.json()


def _post(path: str, token: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.post(url, headers=_headers(token), json=(payload or {}), timeout=300)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text}")
    return r.json()


def _patch(path: str, token: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.patch(url, headers=_headers(token), json=(payload or {}), timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text}")
    return r.json()


def _delete(path: str, token: Optional[str] = None) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.delete(url, headers=_headers(token), timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text}")
    return r.json()


# -------------------------
# Auth
# -------------------------
def signup(email: str, confirm_email: str, password: str) -> Any:
    return _post(
        "/auth/signup",
        None,
        {"email": email, "confirm_email": confirm_email, "password": password},
    )


def login(email: str, password: str) -> Any:
    return _post("/auth/login", None, {"email": email, "password": password})


# -------------------------
# Profile
# -------------------------
def get_profile(token: str) -> Any:
    return _get("/profile", token)


def save_profile(token: str, profile: Dict[str, Any]) -> Any:
    return _post("/profile", token, {"profile": profile})


# -------------------------
# Job Description Highlights
# -------------------------
def generate_jd_highlights(
    token: str,
    company: str,
    job_title: str,
    job_description: str,
    model: str = "llama3.1",
) -> Any:
    return _post(
        "/jd/highlights",
        token,
        {
            "company": company,
            "job_title": job_title,
            "job_description": job_description,
            "model": model,
        },
    )


# -------------------------
# ATS Score
# -------------------------
def score_ats(token: str, draft_id: str, model: str = "llama3.1") -> Any:
    return _post(
        "/ats/score",
        token,
        {
            "draft_id": draft_id,
            "model": model,
        },
    )


# -------------------------
# Senior Recruiter Check
# -------------------------
def recruiter_check(token: str, draft_id: str, model: str = "llama3.1") -> Any:
    return _post(
        "/recruiter/check",
        token,
        {
            "draft_id": draft_id,
            "model": model,
        },
    )


# -------------------------
# Easy to Read / Readability Check
# -------------------------
def readability_check(token: str, draft_id: str, model: str = "llama3.1") -> Any:
    return _post(
        "/readability/check",
        token,
        {
            "draft_id": draft_id,
            "model": model,
        },
    )


# -------------------------
# CV
# -------------------------
def list_drafts(token: str) -> Any:
    return _get("/cv/drafts", token)


def get_draft(token: str, draft_id: str) -> Any:
    return _get(f"/cv/drafts/{draft_id}", token)


def generate_cv(
    token: str,
    company: str,
    job_title: str,
    job_description: str,
    model: str = "llama3.1",
) -> Any:
    return _post(
        "/cv/generate",
        token,
        {
            "company": company,
            "job_title": job_title,
            "job_description": job_description,
            "model": model,
        },
    )


def save_cv_edited(token: str, draft_id: str, edited: Dict[str, Any]) -> Any:
    return _post("/cv/save_edited", token, {"draft_id": draft_id, "edited": edited})


def export_cv_docx(token: str, draft_id: str) -> Any:
    return _get(f"/cv/export/{draft_id}/docx", token)


def export_cv_pdf(token: str, draft_id: str) -> Any:
    return _get(f"/cv/export/{draft_id}/pdf", token)


# -------------------------
# Cover Letter
# -------------------------
def generate_cover(token: str, draft_id: str, model: str = "llama3.1") -> Any:
    return _post("/cover/generate", token, {"draft_id": draft_id, "model": model})


def save_cover_edited(token: str, draft_id: str, cover_letter: str) -> Any:
    return _post("/cover/save_edited", token, {"draft_id": draft_id, "cover_letter": cover_letter})


def export_cover_docx(token: str, draft_id: str) -> Any:
    return _get(f"/cover/export/{draft_id}/docx", token)


def export_cover_pdf(token: str, draft_id: str) -> Any:
    return _get(f"/cover/export/{draft_id}/pdf", token)


# -------------------------
# Tracker
# -------------------------
def tracker_meta(token: str) -> Any:
    return _get("/tracker/meta", token)


def tracker_add_from_draft(token: str, payload: Dict[str, Any]) -> Any:
    return _post("/tracker/add_from_draft", token, payload)


def tracker_list(token: str) -> Any:
    return _get("/tracker/list", token)


def tracker_get(token: str, app_id: int) -> Any:
    return _get(f"/tracker/item/{app_id}", token)


def tracker_patch(token: str, app_id: int, patch: Dict[str, Any]) -> Any:
    return _patch(f"/tracker/item/{app_id}", token, patch)


def tracker_delete(token: str, app_id: int) -> Any:
    return _delete(f"/tracker/item/{app_id}", token)


def tracker_duplicate_check(token: str, company: str, limit: int = 50) -> Any:
    return _post("/tracker/duplicate_check", token, {"company": company, "limit": limit})


def tracker_followups(token: str, days: int = 3) -> Any:
    return _get("/tracker/followups", token, params={"days": days})


def tracker_due(token: str) -> Any:
    return _get("/tracker/due", token)


def tracker_export_rows(token: str) -> Any:
    return _get("/tracker/export", token)