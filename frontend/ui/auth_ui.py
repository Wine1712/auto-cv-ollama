# ui/auth_ui.py
import streamlit as st
from services.api_client import login, signup, get_profile
from services.state import logout


def auth_gate():
    """
    If not logged in -> show login/signup and stop.
    """
    if st.session_state.get("token"):
        return

    st.title("🔐 AutoCV Login")
    st.caption("Login to generate CV / cover letter and track your applications.")

    tab1, tab2 = st.tabs(["Login", "Create account"])

    # =========================
    # LOGIN
    # =========================
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login"):
            try:
                resp = login(email.strip(), password)

                # Save token
                st.session_state.token = resp["access_token"]
                st.session_state.email = email.strip().lower()

                # Load profile immediately after login
                try:
                    profile_resp = get_profile(st.session_state.token) or {}
                    profile = profile_resp.get("profile", {}) or {}

                    st.session_state.profile = profile
                    st.session_state.loaded_profile = profile
                except Exception:
                    st.session_state.profile = {}
                    st.session_state.loaded_profile = {}

                st.success("Logged in ✅")
                st.rerun()

            except Exception as e:
                st.error(str(e))

    # =========================
    # SIGNUP
    # =========================
    with tab2:
        email2 = st.text_input("Email", key="reg_email")
        email3 = st.text_input("Confirm Email", key="reg_email2")
        pass2 = st.text_input("Password", type="password", key="reg_pass")

        if st.button("Create account"):
            try:
                resp = signup(email2.strip(), email3.strip(), pass2)
                st.success("Account created ✅")
                st.info(f"Verify link (local dev): {resp.get('verify_link','')}")
            except Exception as e:
                st.error(str(e))

    st.stop()