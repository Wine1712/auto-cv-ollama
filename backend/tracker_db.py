# backend/tracker_db.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reuse your existing DB path if you want everything in one file DB.
# If your backend/db.py already defines DB_PATH, you can import it instead.
# To keep this file standalone, we default to "auto_cv.db" (change if needed).
DB_PATH = str(Path(__file__).resolve().parents[1] / "auto_cv.db")


# -------------------------
# Helpers
# -------------------------
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    # check_same_thread False to match Streamlit / FastAPI usage patterns
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # ensure FK works if we add them later
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    return conn


def _norm_company(name: str) -> str:
    # Normalize for duplicate detection: lowercase + collapse whitespace
    s = (name or "").strip().lower()
    s = " ".join(s.split())
    return s


# -------------------------
# Schema init
# -------------------------
def init_tracker_db() -> None:
    """
    Creates tables for tracking job applications.
    Stores data per user (email) to match your auth system.
    """
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                company TEXT NOT NULL,
                company_norm TEXT NOT NULL,
                role TEXT NOT NULL,
                job_type TEXT,
                location TEXT,
                job_link TEXT,
                source TEXT,
                status TEXT NOT NULL,
                applied_date TEXT NOT NULL,
                followup_date TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Indexes for speed (company duplicate check + per-user queries)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_user_email ON applications(user_email)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_company_norm ON applications(user_email, company_norm)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_followup ON applications(user_email, followup_date)"
        )


# -------------------------
# CRUD
# -------------------------
def insert_application(user_email: str, data: Dict[str, Any]) -> int:
    """
    Insert one application row.
    Required fields in data: company, role, status, applied_date, followup_date
    """
    user_email = (user_email or "").strip().lower()
    company = str(data.get("company") or "").strip()
    role = str(data.get("role") or "").strip()

    if not user_email:
        raise ValueError("user_email is required")
    if not company:
        raise ValueError("company is required")
    if not role:
        raise ValueError("role is required")

    status = str(data.get("status") or "Applied").strip() or "Applied"

    applied_date = str(data.get("applied_date") or "").strip()
    followup_date = str(data.get("followup_date") or "").strip()
    if not applied_date:
        raise ValueError("applied_date is required (ISO string)")
    if not followup_date:
        raise ValueError("followup_date is required (ISO string)")

    now = _utc_now_iso()
    row = {
        "user_email": user_email,
        "company": company,
        "company_norm": _norm_company(company),
        "role": role,
        "job_type": str(data.get("job_type") or "").strip() or None,
        "location": str(data.get("location") or "").strip() or None,
        "job_link": str(data.get("job_link") or "").strip() or None,
        "source": str(data.get("source") or "").strip() or None,
        "status": status,
        "applied_date": applied_date,
        "followup_date": followup_date,
        "notes": str(data.get("notes") or "").strip() or None,
        "created_at": now,
        "updated_at": now,
    }

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO applications (
                user_email, company, company_norm, role, job_type, location,
                job_link, source, status, applied_date, followup_date, notes,
                created_at, updated_at
            ) VALUES (
                :user_email, :company, :company_norm, :role, :job_type, :location,
                :job_link, :source, :status, :applied_date, :followup_date, :notes,
                :created_at, :updated_at
            )
            """,
            row,
        )
        return int(cur.lastrowid)


def fetch_application_by_id(user_email: str, app_id: int) -> Optional[Dict[str, Any]]:
    user_email = (user_email or "").strip().lower()
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM applications WHERE user_email = ? AND id = ?",
            (user_email, int(app_id)),
        ).fetchone()
        return dict(r) if r else None


def list_applications(user_email: str) -> List[Dict[str, Any]]:
    user_email = (user_email or "").strip().lower()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE user_email = ? ORDER BY created_at DESC",
            (user_email,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_application(user_email: str, app_id: int, patch: Dict[str, Any]) -> bool:
    """
    Patch fields. If company is updated, company_norm updates too.
    Returns True if updated, False if not found.
    """
    user_email = (user_email or "").strip().lower()
    existing = fetch_application_by_id(user_email, app_id)
    if not existing:
        return False

    allowed = {
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
    }

    updates: Dict[str, Any] = {}
    for k, v in (patch or {}).items():
        if k not in allowed:
            continue
        if k in {"company", "role", "job_type", "location", "job_link", "source", "status", "notes"}:
            vv = str(v or "").strip()
            updates[k] = vv if vv else None
        else:
            # dates as-is (ISO string)
            updates[k] = str(v or "").strip() if v is not None else None

    if "company" in updates and updates["company"]:
        updates["company_norm"] = _norm_company(str(updates["company"]))

    updates["updated_at"] = _utc_now_iso()

    if not updates:
        return True

    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["user_email"] = user_email
    updates["id"] = int(app_id)

    with get_conn() as conn:
        cur = conn.execute(
            f"""
            UPDATE applications
            SET {set_clause}
            WHERE user_email = :user_email AND id = :id
            """,
            updates,
        )
        return cur.rowcount > 0


def delete_application(user_email: str, app_id: int) -> bool:
    user_email = (user_email or "").strip().lower()
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM applications WHERE user_email = ? AND id = ?",
            (user_email, int(app_id)),
        )
        return cur.rowcount > 0


# -------------------------
# Duplicate company helper
# -------------------------
def company_history(user_email: str, company: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Returns previous applications for the same company (normalized match).
    Used for "duplicate company alarm".
    """
    user_email = (user_email or "").strip().lower()
    cn = _norm_company(company)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM applications
            WHERE user_email = ? AND company_norm = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_email, cn, int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]


# -------------------------
# Follow-up queries
# -------------------------
def list_followups_due(user_email: str, *, iso_today: str) -> List[Dict[str, Any]]:
    """
    Returns applications with followup_date <= iso_today (string compare works if ISO8601).
    """
    user_email = (user_email or "").strip().lower()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM applications
            WHERE user_email = ?
              AND followup_date <= ?
              AND status NOT IN ('Rejected', 'Offer', 'Closed')
            ORDER BY followup_date ASC
            """,
            (user_email, iso_today),
        ).fetchall()
        return [dict(r) for r in rows]


def list_followups_window(user_email: str, *, iso_start: str, iso_end: str) -> List[Dict[str, Any]]:
    """
    Returns applications with followup_date in [iso_start, iso_end].
    """
    user_email = (user_email or "").strip().lower()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM applications
            WHERE user_email = ?
              AND followup_date >= ?
              AND followup_date <= ?
              AND status NOT IN ('Rejected', 'Offer', 'Closed')
            ORDER BY followup_date ASC
            """,
            (user_email, iso_start, iso_end),
        ).fetchall()
        return [dict(r) for r in rows]