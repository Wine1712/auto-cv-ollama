# ui/cover_ui.py
import streamlit as st
from services.api_client import (
    list_drafts,
    generate_cover,
    save_cover_edited,
    export_cover_docx,
    export_cover_pdf,
)


def page_cover():
    st.header("📝 Cover Letter")

    token = st.session_state.token

    st.subheader("Choose a draft (uses CV + Job Description)")

    drafts = []
    try:
        drafts = list_drafts(token) or []
    except Exception as e:
        st.error(str(e))

    draft_map = {
        d.get("draft_name", d["draft_id"]): d["draft_id"]
        for d in drafts
    }

    reverse_draft_map = {
        d["draft_id"]: d.get("draft_name", d["draft_id"])
        for d in drafts
    }

    options = [""] + list(draft_map.keys())

    current_id = st.session_state.get("selected_draft_id", "")
    current_name = reverse_draft_map.get(current_id, "")
    selected_index = options.index(current_name) if current_name in options else 0

    selected = st.selectbox(
        "Draft",
        options,
        index=selected_index,
        key="cover_selected_draft",
    )

    if selected:
        st.session_state.selected_draft_id = draft_map[selected]

    model = st.text_input("Model", value="llama3.1", key="cover_model")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Generate cover letter", key="btn_generate_cover"):
            try:
                if not st.session_state.get("selected_draft_id"):
                    st.error("Select a draft first.")
                else:
                    resp = generate_cover(
                        token,
                        st.session_state.selected_draft_id,
                        model=model,
                    )
                    st.session_state.last_cover = resp.get("cover_letter") or ""
                    st.success("Generated ✅")
            except Exception as e:
                st.error(str(e))

    cover = st.session_state.get("last_cover") or ""
    cover_txt = st.text_area(
        "Cover letter text",
        value=cover,
        height=520,
        key="cover_text",
    )

    c3, c4, c5 = st.columns(3)

    with c3:
        if st.button("Save edited cover", key="btn_save_cover"):
            try:
                if not st.session_state.get("selected_draft_id"):
                    st.error("Select a draft first.")
                else:
                    save_cover_edited(
                        token,
                        st.session_state.selected_draft_id,
                        cover_txt,
                    )
                    st.session_state.last_cover = cover_txt
                    st.success("Saved ✅")
            except Exception as e:
                st.error(str(e))

    with c4:
        if st.button("Export cover DOCX", key="btn_export_cover_docx"):
            try:
                if not st.session_state.get("selected_draft_id"):
                    st.error("Select a draft first.")
                else:
                    resp = export_cover_docx(token, st.session_state.selected_draft_id)
                    st.success(f"DOCX ready ✅ {resp.get('filename', '')}")
                    st.code(resp.get("file_path", ""))
            except Exception as e:
                st.error(str(e))

    with c5:
        if st.button("Export cover PDF", key="btn_export_cover_pdf"):
            try:
                if not st.session_state.get("selected_draft_id"):
                    st.error("Select a draft first.")
                else:
                    resp = export_cover_pdf(token, st.session_state.selected_draft_id)
                    st.success(f"PDF ready ✅ {resp.get('filename', '')}")
                    st.code(resp.get("file_path", ""))
            except Exception as e:
                st.error(str(e))