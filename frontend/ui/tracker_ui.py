# ui/tracker_ui.py
import streamlit as st
import pandas as pd

from services.api_client import (
    tracker_list, tracker_followups, tracker_due,
    tracker_patch, tracker_delete, tracker_export_rows,
    tracker_meta
)

def page_tracker():
    st.header("📌 Tracker")

    token = st.session_state.token

    # meta
    try:
        meta = tracker_meta(token)
        STATUSES = meta.get("statuses", [])
        JOB_TYPES = meta.get("job_types", [])
    except Exception:
        STATUSES = []
        JOB_TYPES = []

    # Followups
    st.subheader("⏰ Follow-ups")
    days = st.number_input("Soon window (days)", min_value=1, max_value=30, value=3)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refresh followups"):
            try:
                st.session_state["_followups"] = tracker_followups(token, days=int(days))
                st.session_state["_due"] = tracker_due(token)
            except Exception as e:
                st.error(str(e))

    followups = st.session_state.get("_followups") or {}
    overdue = followups.get("overdue") or []
    soon = followups.get("soon") or []

    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### 🔥 Overdue")
        st.dataframe(pd.DataFrame(overdue), use_container_width=True) if overdue else st.info("No overdue ✅")
    with colB:
        st.markdown(f"#### ✅ Due in next {int(days)} days")
        st.dataframe(pd.DataFrame(soon), use_container_width=True) if soon else st.info("No due soon ✅")

    st.markdown("#### 📌 Due today or earlier")
    due = st.session_state.get("_due") or []
    st.dataframe(pd.DataFrame(due), use_container_width=True) if due else st.success("Nothing due today 🎉")

    st.divider()
    st.subheader("📋 Applications")

    try:
        rows = tracker_list(token) or []
    except Exception as e:
        st.error(str(e))
        rows = []

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if df.empty:
        st.info("No applications yet.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("✏️ Edit / Close / Delete")

    default_id = int(df["id"].iloc[0])
    app_id = st.number_input("Application ID", min_value=1, value=default_id)

    row = df[df["id"] == int(app_id)]
    if row.empty:
        st.error("ID not found.")
        return
    row = row.iloc[0].to_dict()

    with st.form("edit_app_form"):
        e_company = st.text_input("Company", value=row.get("company",""))
        e_role = st.text_input("Role", value=row.get("role",""))
        e_jobtype = st.selectbox("Job type", JOB_TYPES or ["Full-time"], index=(JOB_TYPES.index(row.get("job_type")) if JOB_TYPES and row.get("job_type") in JOB_TYPES else 0))
        e_location = st.text_input("Location", value=row.get("location","") or "")
        e_job_link = st.text_input("Job link", value=row.get("job_link","") or "")
        e_source = st.text_input("Source", value=row.get("source","") or "")
        e_status = st.selectbox("Status", STATUSES or ["Applied"], index=(STATUSES.index(row.get("status")) if STATUSES and row.get("status") in STATUSES else 0))
        e_applied = st.text_input("Applied date (ISO)", value=row.get("applied_date","") or "")
        e_followup = st.text_input("Follow-up date (ISO)", value=row.get("followup_date","") or "")
        e_notes = st.text_area("Notes", value=row.get("notes","") or "")

        c1, c2, c3 = st.columns(3)
        save_btn = c1.form_submit_button("Save")
        close_btn = c2.form_submit_button("Mark Closed")
        delete_btn = c3.form_submit_button("Delete")

        if save_btn:
            try:
                patch = {
                    "company": e_company,
                    "role": e_role,
                    "job_type": e_jobtype,
                    "location": e_location,
                    "job_link": e_job_link,
                    "source": e_source,
                    "status": e_status,
                    "applied_date": e_applied,
                    "followup_date": e_followup,
                    "notes": e_notes,
                }
                tracker_patch(token, int(app_id), patch)
                st.success("Updated ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

        if close_btn:
            try:
                tracker_patch(token, int(app_id), {"status": "Closed"})
                st.success("Closed ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

        if delete_btn:
            try:
                tracker_delete(token, int(app_id))
                st.success("Deleted ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("⬇️ Export CSV")

    if st.button("Prepare CSV data"):
        try:
            resp = tracker_export_rows(token)
            rows = resp.get("rows") or []
            df2 = pd.DataFrame(rows)
            st.session_state["_export_df"] = df2
            st.success("Ready ✅")
        except Exception as e:
            st.error(str(e))

    df_export = st.session_state.get("_export_df")
    if isinstance(df_export, pd.DataFrame) and not df_export.empty:
        csv_bytes = df_export.to_csv(index=False).encode("utf-8")
        st.download_button("Download tracker.csv", data=csv_bytes, file_name="tracker.csv", mime="text/csv")