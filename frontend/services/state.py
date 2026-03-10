# services/state.py
import streamlit as st

def init_state():
    """
    Central place to initialize Streamlit session state keys.
    """
    defaults = {
        "token": None,
        "email": None,
        "selected_draft_id": None,
        "last_cv": None,
        "last_cover": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def logout():
    st.session_state.token = None
    st.session_state.email = None
    st.session_state.selected_draft_id = None
    st.session_state.last_cv = None
    st.session_state.last_cover = None