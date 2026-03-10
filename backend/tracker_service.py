# backend/tracker_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.tracker_db import (
    init_tracker_db,
    insert_application,
    fetch_application_by_id,
    list_applications,
    update_application,
    delete_application,
    company_history,
    list_followups_due,
    list_followups_window,
)

# Keep statuses aligned with your Streamlit tracker UI
STATUSES = ["Applied", "Screening", "Interview", "Assessment", "Offer", "Rejected", "Closed"]
JOB_TYPES = ["Full-time", "Part-time", "Casual", "Contract", "Internship", "Other"]


# -------------------------
# Date helpers (ISO strings)
# -------------------------
def iso_date(d: date) -> str:
    # store as ISO datetime string for easy sorting/compare
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()


def utc_today_date() -> date:
    return datetime.now(timezone.utc).date()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------------------
# Init
# -------------------------
def ensure_tracker_ready() -> None:
    init_tracker_db()


# -------------------------
# High-level operations
# -------------------------
@dataclass(frozen=True)
class AddFromDraftInput:
    user_email: str
    company: str
    role: str
    job_link: str = ""
    location: str = ""
    source: str = "AutoCV"
    job_type: str = "Full-time"
    status: str = "Applied"
    applied_date: Optional[str] = None          # ISO string
    followup_in_days: int = 7
    notes: str = ""


def add_application_from_draft(inp: AddFromDraftInput) -> Dict[str, Any]:
    """
    Adds an application row (used by your AutoCV app after Generate CV).
    Also returns duplicate alarm info for that company.
    """
    ensure_tracker_ready()

    user_email = (inp.user_email or "").strip().lower()
    if not user_email:
        raise ValueError("user_email is required")

    company = (inp.company or "").strip()
    role = (inp.role or "").strip()
    if not company:
        raise ValueError("company is required")
    if not role:
        raise ValueError("role is required")

    status = (inp.status or "Applied").strip()
    if status not in STATUSES:
        status = "Applied"

    job_type = (inp.job_type or "Full-time").strip()
    if job_type not in JOB_TYPES:
        job_type = "Full-time"

    # Applied date default: today (UTC)
    if inp.applied_date and str(inp.applied_date).strip():
        applied_iso = str(inp.applied_date).strip()
        # best-effort parse to normalize to ISO
        applied_dt = _parse_any_iso_date(applied_iso) or datetime.now(timezone.utc)
    else:
        applied_dt = datetime.now(timezone.utc)
        applied_iso = applied_dt.isoformat()

    followup_dt = applied_dt + timedelta(days=int(inp.followup_in_days))
    followup_iso = followup_dt.isoformat()

    # Duplicate alarm (history BEFORE insert)
    hist = company_history(user_email, company, limit=20)

    app_id = insert_application(
        user_email=user_email,
        data={
            "company": company,
            "role": role,
            "job_type": job_type,
            "location": (inp.location or "").strip(),
            "job_link": (inp.job_link or "").strip(),
            "source": (inp.source or "AutoCV").strip(),
            "status": status,
            "applied_date": applied_iso,
            "followup_date": followup_iso,
            "notes": (inp.notes or "").strip(),
        },
    )

    created = fetch_application_by_id(user_email, app_id) or {}
    return {
        "application": created,
        "duplicate_alarm": {
            "is_duplicate": bool(hist),
            "matches": hist,
        },
    }


def list_my_applications(user_email: str) -> List[Dict[str, Any]]:
    ensure_tracker_ready()
    return list_applications((user_email or "").strip().lower())


def get_application(user_email: str, app_id: int) -> Optional[Dict[str, Any]]:
    ensure_tracker_ready()
    return fetch_application_by_id((user_email or "").strip().lower(), int(app_id))


def patch_application(user_email: str, app_id: int, patch: Dict[str, Any]) -> bool:
    ensure_tracker_ready()
    return update_application((user_email or "").strip().lower(), int(app_id), patch or {})


def remove_application(user_email: str, app_id: int) -> bool:
    ensure_tracker_ready()
    return delete_application((user_email or "").strip().lower(), int(app_id))


def duplicate_company_alarm(user_email: str, company: str, limit: int = 50) -> Dict[str, Any]:
    ensure_tracker_ready()
    hist = company_history((user_email or "").strip().lower(), company, limit=limit)
    return {"is_duplicate": bool(hist), "matches": hist}


# -------------------------
# Follow-up services
# -------------------------
def followups_due_today_or_earlier(user_email: str) -> List[Dict[str, Any]]:
    ensure_tracker_ready()
    iso_today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    return list_followups_due((user_email or "").strip().lower(), iso_today=iso_today)


def followups_in_next_days(user_email: str, days: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns:
      - overdue: followup < today
      - soon: today <= followup <= today+days
    """
    ensure_tracker_ready()
    user_email = (user_email or "").strip().lower()

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = today + timedelta(days=int(days), hours=23, minutes=59, seconds=59)

    # Pull a window that includes overdue + soon
    # We'll query window only for "soon", and query due list for overdue.
    overdue = _filter_overdue(followups_due_today_or_earlier(user_email), today)

    soon_rows = list_followups_window(
        user_email,
        iso_start=today.isoformat(),
        iso_end=end.isoformat(),
    )

    return {"overdue": overdue, "soon": soon_rows}


def _filter_overdue(rows: List[Dict[str, Any]], today_start: datetime) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        fd = _parse_any_iso_date(str(r.get("followup_date") or ""))
        if fd and fd < today_start:
            out.append(r)
    return out


# -------------------------
# CSV export helpers
# -------------------------
def export_rows_for_csv(user_email: str) -> List[Dict[str, Any]]:
    """
    Return rows in a clean, CSV-friendly shape (no sqlite Row objects).
    Your Streamlit layer can turn this into pandas DF and st.download_button.
    """
    rows = list_my_applications(user_email)
    # Optional: reorder / select columns
    cols = [
        "id",
        "company",
        "role",
        "job_type",
        "location",
        "job_link",
        "source",
        "status",
        "applied_date",
        "followup_date",
        "notes",
        "created_at",
        "updated_at",
        "user_email",
    ]
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({k: r.get(k) for k in cols})
    return out


# -------------------------
# Parsing
# -------------------------
def _parse_any_iso_date(s: str) -> Optional[datetime]:
    """
    Best-effort parse for stored ISO strings.
    """
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None