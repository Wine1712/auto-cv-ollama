# backend/tracker_routes.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from backend.auth import decode_token
from backend.tracker_service import (
    ensure_tracker_ready,
    add_application_from_draft,
    list_my_applications,
    get_application,
    patch_application,
    remove_application,
    duplicate_company_alarm,
    followups_in_next_days,
    followups_due_today_or_earlier,
    export_rows_for_csv,
    AddFromDraftInput,
    STATUSES,
    JOB_TYPES,
)

router = APIRouter(prefix="/tracker", tags=["tracker"])


# ----------------------------
# Auth helper (same as api.py)
# ----------------------------
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


# ----------------------------
# Request models
# ----------------------------
class TrackerAddFromDraftRequest(BaseModel):
    company: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    job_link: str = ""
    location: str = ""
    source: str = "AutoCV"
    job_type: str = "Full-time"
    status: str = "Applied"
    applied_date: Optional[str] = None
    followup_in_days: int = 7
    notes: str = ""


class TrackerPatchRequest(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    job_type: Optional[str] = None
    location: Optional[str] = None
    job_link: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    applied_date: Optional[str] = None
    followup_date: Optional[str] = None
    notes: Optional[str] = None


class TrackerDuplicateCheckRequest(BaseModel):
    company: str = Field(..., min_length=1)
    limit: int = 50


# ----------------------------
# Routes
# ----------------------------


@router.get("/meta")
def tracker_meta():
    return {"statuses": STATUSES, "job_types": JOB_TYPES}


@router.post("/add_from_draft")
def tracker_add_from_draft(req: TrackerAddFromDraftRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    # Soft validation of enums
    job_type = (req.job_type or "Full-time").strip()
    if job_type not in JOB_TYPES:
        job_type = "Full-time"

    status = (req.status or "Applied").strip()
    if status not in STATUSES:
        status = "Applied"

    try:
        result = add_application_from_draft(
            AddFromDraftInput(
                user_email=email,
                company=req.company,
                role=req.role,
                job_link=req.job_link,
                location=req.location,
                source=req.source,
                job_type=job_type,
                status=status,
                applied_date=req.applied_date,
                followup_in_days=int(req.followup_in_days),
                notes=req.notes,
            )
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
def tracker_list(authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    return list_my_applications(email)


@router.get("/item/{app_id}")
def tracker_get(app_id: int, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    row = get_application(email, int(app_id))
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    return row


@router.patch("/item/{app_id}")
def tracker_patch(app_id: int, req: TrackerPatchRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)

    patch: Dict[str, Any] = {k: v for k, v in req.model_dump().items() if v is not None}

    # Soft validate enums if present
    if "job_type" in patch:
        jt = str(patch["job_type"] or "").strip()
        if jt and jt not in JOB_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid job_type. Must be one of: {JOB_TYPES}")
        patch["job_type"] = jt

    if "status" in patch:
        st = str(patch["status"] or "").strip()
        if st and st not in STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {STATUSES}")
        patch["status"] = st

    ok = patch_application(email, int(app_id), patch)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"ok": True}


@router.delete("/item/{app_id}")
def tracker_delete(app_id: int, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    ok = remove_application(email, int(app_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"ok": True}


@router.post("/duplicate_check")
def tracker_duplicate_check(req: TrackerDuplicateCheckRequest, authorization: Optional[str] = Header(default=None)):
    email = _get_email_from_auth(authorization)
    return duplicate_company_alarm(email, req.company, limit=int(req.limit))


@router.get("/followups")
def tracker_followups(days: int = 3, authorization: Optional[str] = Header(default=None)):
    """
    Returns:
      { "overdue": [...], "soon": [...] }
    """
    email = _get_email_from_auth(authorization)
    return followups_in_next_days(email, days=int(days))


@router.get("/due")
def tracker_due(authorization: Optional[str] = Header(default=None)):
    """
    Returns follow-ups due today or earlier (including overdue + today).
    """
    email = _get_email_from_auth(authorization)
    return followups_due_today_or_earlier(email)


@router.get("/export")
def tracker_export_rows(authorization: Optional[str] = Header(default=None)):
    """
    Returns JSON rows for CSV export.
    Your Streamlit UI can convert to pandas and let user download CSV.
    """
    email = _get_email_from_auth(authorization)
    rows = export_rows_for_csv(email)
    return {"rows": rows}