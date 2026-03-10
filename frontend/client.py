import requests
from typing import Dict, Any, List, Optional

API = "http://127.0.0.1:8000"


class APIError(Exception):
    """Friendly error raised when backend returns an error response."""
    pass


def _raise_api_error(r: requests.Response) -> None:
    """
    Convert FastAPI error responses into a clean message for Streamlit.
    FastAPI typically returns: {"detail": "..."} or {"detail": {...}}
    """
    try:
        data = r.json()
        detail = data.get("detail", None)
        if isinstance(detail, str):
            raise APIError(detail)
        if detail is not None:
            raise APIError(str(detail))
        raise APIError(r.text)
    except ValueError:
        # Not JSON
        raise APIError(r.text)


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# -----------------------
# Auth
# -----------------------
def signup(email: str, confirm_email: str, password: str) -> Dict[str, Any]:
    r = requests.post(
        f"{API}/auth/signup",
        json={"email": email, "confirm_email": confirm_email, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def verify_email(token: str) -> Dict[str, Any]:
    r = requests.get(f"{API}/auth/verify/{token}", timeout=30)
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def login(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        _raise_api_error(r)

    data = r.json()
    # backend returns {"access_token": "...", "token_type": "bearer"}
    token = data.get("access_token") or data.get("token")
    if not token:
        raise APIError(f"Login response missing token field: {data}")
    return token


# -----------------------
# Profile
# -----------------------
def get_profile(token: str) -> Dict[str, Any]:
    r = requests.get(f"{API}/profile", headers=_headers(token), timeout=30)
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def save_profile(token: str, profile: Dict[str, Any]) -> None:
    r = requests.post(
        f"{API}/profile",
        headers=_headers(token),
        json={"profile": profile},
        timeout=30,
    )
    if r.status_code != 200:
        _raise_api_error(r)


# -----------------------
# CV
# -----------------------
def generate_cv(
    token: str,
    company: str,
    job_title: str,
    job_description: str,
    model: str = "llama3.1",
) -> Dict[str, Any]:
    r = requests.post(
        f"{API}/cv/generate",
        headers=_headers(token),
        json={
            "company": company,
            "job_title": job_title,
            "job_description": job_description,
            "model": model,
        },
        timeout=240,
    )
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def list_drafts(token: str) -> List[Dict[str, Any]]:
    r = requests.get(f"{API}/cv/drafts", headers=_headers(token), timeout=30)
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def get_draft(token: str, draft_id: str) -> Dict[str, Any]:
    r = requests.get(f"{API}/cv/drafts/{draft_id}", headers=_headers(token), timeout=30)
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def save_edited(token: str, draft_id: str, edited: Dict[str, Any]) -> None:
    r = requests.post(
        f"{API}/cv/save_edited",
        headers=_headers(token),
        json={"draft_id": draft_id, "edited": edited},
        timeout=30,
    )
    if r.status_code != 200:
        _raise_api_error(r)


def export_docx(token: str, draft_id: str) -> Dict[str, Any]:
    r = requests.get(f"{API}/cv/export/{draft_id}/docx", headers=_headers(token), timeout=60)
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()


def export_pdf(token: str, draft_id: str) -> Dict[str, Any]:
    r = requests.get(f"{API}/cv/export/{draft_id}/pdf", headers=_headers(token), timeout=60)
    if r.status_code != 200:
        _raise_api_error(r)
    return r.json()