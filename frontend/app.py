# app.py
import streamlit as st

from services.state import init_state
from services.api_client import get_profile
from ui.auth_ui import auth_gate
from ui.profile_ui import page_profile
from ui.cv_ui import page_cv
from ui.cover_ui import page_cover
from ui.tracker_ui import page_tracker

st.set_page_config(page_title="AutoCV + Tracker", page_icon="🧾", layout="wide")

init_state()

# login gate (stops if not logged in)
auth_gate()

# Load profile once after login so it is available across all pages
if st.session_state.get("token") and not st.session_state.get("profile_bootstrapped", False):
    try:
        resp = get_profile(st.session_state.token) or {}
        profile = resp.get("profile", {}) or {}
        st.session_state.profile = profile
        st.session_state.loaded_profile = profile
    except Exception:
        st.session_state.profile = {}
        st.session_state.loaded_profile = {}
    st.session_state.profile_bootstrapped = True

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Generate CV", "Cover Letter", "Tracker", "Master Profile"],
    index=0,
)

if page == "Generate CV":
    page_cv()
elif page == "Cover Letter":
    page_cover()
elif page == "Tracker":
    page_tracker()
elif page == "Master Profile":
    page_profile()