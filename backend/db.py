# backend/db.py
from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data_local"
USERS_CSV = DATA_DIR / "users.csv"
PROFILES_DIR = DATA_DIR / "profiles"
DRAFTS_DIR = DATA_DIR / "drafts"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

USER_FIELDS = ["email", "password_hash", "verified", "verify_token", "created_at"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _email_key(email: str) -> str:
    e = (email or "").strip().lower()
    return re.sub(r"[^a-z0-9._-]+", "_", e)


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


# ---------------- Users (CSV) ----------------
def init_db() -> None:
    if not USERS_CSV.exists():
        with USERS_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=USER_FIELDS)
            writer.writeheader()


def get_all_users() -> List[Dict[str, str]]:
    init_db()
    with USERS_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_user(email: str) -> Optional[Dict[str, str]]:
    email = (email or "").strip().lower()
    if not email:
        return None
    for u in get_all_users():
        if (u.get("email") or "").strip().lower() == email:
            return u
    return None


def save_user(email: str, password_hash, verify_token: str) -> None:
    init_db()
    email = (email or "").strip().lower()

    if isinstance(password_hash, (bytes, bytearray)):
        password_hash_str = password_hash.decode("utf-8")
    else:
        password_hash_str = str(password_hash)

    with USERS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=USER_FIELDS)
        writer.writerow(
            {
                "email": email,
                "password_hash": password_hash_str,
                "verified": "False",
                "verify_token": verify_token,
                "created_at": _utc_now_iso(),
            }
        )


def verify_user(token: str) -> bool:
    init_db()
    rows = get_all_users()
    changed = False

    for r in rows:
        if r.get("verify_token") == token:
            r["verified"] = "True"
            changed = True

    with USERS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=USER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return changed


# ---------------- Profiles (JSON per user) ----------------
def _profile_path(email: str) -> Path:
    return PROFILES_DIR / f"{_email_key(email)}.json"


def load_profile(email: str) -> Dict[str, Any]:
    p = _profile_path(email)
    if not p.exists():
        return {}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        meta_email = ((data.get("_meta") or {}).get("email") or "").strip().lower()
        if meta_email and meta_email != (email or "").strip().lower():
            return {}
        return data
    except Exception:
        return {}


def save_profile(email: str, profile: Dict[str, Any]) -> None:
    email_norm = (email or "").strip().lower()
    p = _profile_path(email_norm)

    payload = dict(profile or {})
    payload["_meta"] = {
        "email": email_norm,
        "updated_at": _utc_now_iso(),
    }

    _atomic_write_json(p, payload)


# ---------------- Drafts (JSON per user folder) ----------------
def _drafts_user_dir(email: str) -> Path:
    d = DRAFTS_DIR / _email_key(email)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_draft(email: str, draft_id: str, draft: Dict[str, Any]) -> None:
    email_norm = (email or "").strip().lower()
    ddir = _drafts_user_dir(email_norm)
    path = ddir / f"{draft_id}.json"

    payload = dict(draft or {})
    meta = payload.get("_meta") or {}
    meta.update(
        {
            "email": email_norm,
            "draft_id": draft_id,
            "updated_at": _utc_now_iso(),
        }
    )
    payload["_meta"] = meta

    _atomic_write_json(path, payload)


def list_drafts(email: str) -> List[Dict[str, Any]]:
    email_norm = (email or "").strip().lower()
    ddir = _drafts_user_dir(email_norm)

    out: List[Dict[str, Any]] = []
    files = sorted(ddir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            meta_email = ((data.get("_meta") or {}).get("email") or "").strip().lower()
            if meta_email and meta_email != email_norm:
                continue
            out.append(data)
        except Exception:
            continue
    return out


def load_draft(email: str, draft_id: str) -> Dict[str, Any]:
    email_norm = (email or "").strip().lower()
    path = _drafts_user_dir(email_norm) / f"{draft_id}.json"
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        meta_email = ((data.get("_meta") or {}).get("email") or "").strip().lower()
        if meta_email and meta_email != email_norm:
            return {}
        return data
    except Exception:
        return {}