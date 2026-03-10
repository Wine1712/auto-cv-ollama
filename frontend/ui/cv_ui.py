# frontend/ui/cv_ui.py
import streamlit as st
from services.api_client import (
    generate_cv,
    generate_jd_highlights,
    score_ats,
    recruiter_check,
    readability_check,
    list_drafts,
    get_draft,
    save_cv_edited,
    export_cv_docx,
    export_cv_pdf,
    tracker_duplicate_check,
    tracker_add_from_draft,
    tracker_meta,
)


def _safe_list(x):
    return x if isinstance(x, list) else []


def _safe_dict(x):
    return x if isinstance(x, dict) else {}


def _join_lines(items):
    if not isinstance(items, list):
        return ""
    return "\n".join([str(x).strip() for x in items if str(x).strip()])


def _split_lines(text):
    return [line.strip() for line in str(text).split("\n") if line.strip()]


def _split_comma_or_lines(text):
    out = []
    for raw_line in str(text).split("\n"):
        parts = [p.strip() for p in raw_line.split(",") if p.strip()]
        out.extend(parts)
    return out


def _box(title: str):
    st.markdown(f"### {title}")


def _master_reference_note(text: str):
    if text and str(text).strip():
        st.caption("Master profile reference")
        st.info(str(text))
    else:
        st.caption("Master profile reference")
        st.info("No saved reference found in your master profile.")


def _render_jd_highlights(jdh: dict):
    st.subheader("🔎 Job Description Highlights")

    st.text_input(
        "Level of Role",
        value=jdh.get("level_of_role", ""),
        key="jdh_level_of_role",
        disabled=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.text_area(
            "Required Skills",
            value="\n".join(jdh.get("required_skills", [])),
            height=150,
            key="jdh_required_skills",
            disabled=True,
        )

        st.text_area(
            "Tools and Technologies",
            value="\n".join(jdh.get("tools_and_technologies", [])),
            height=150,
            key="jdh_tools_and_technologies",
            disabled=True,
        )

        st.text_area(
            "Industry / Domain",
            value="\n".join(jdh.get("industry_domain", [])),
            height=110,
            key="jdh_industry_domain",
            disabled=True,
        )

    with c2:
        st.text_area(
            "Responsibilities",
            value="\n".join(jdh.get("responsibilities", [])),
            height=150,
            key="jdh_responsibilities",
            disabled=True,
        )

        st.text_area(
            "Hidden Keywords (Soft Skills)",
            value="\n".join(jdh.get("hidden_keywords_soft_skills", [])),
            height=150,
            key="jdh_hidden_keywords_soft_skills",
            disabled=True,
        )


def _score_color(score: int) -> str:
    if score >= 85:
        return "green"
    if score >= 70:
        return "orange"
    return "red"


def _render_ats_score(ats: dict):
    st.subheader("🎯 ATS Score Checker")

    overall = int(ats.get("overall_score", 0))
    verdict = ats.get("verdict", "")

    st.markdown(
        f"""
        <div style="
            border:1px solid #ddd;
            border-radius:12px;
            padding:18px;
            margin-bottom:12px;
        ">
            <div style="font-size:15px; color:#666;">Overall ATS Score</div>
            <div style="font-size:42px; font-weight:700; color:{_score_color(overall)};">{overall}/100</div>
            <div style="font-size:16px; font-weight:600;">{verdict}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Keyword Match", ats.get("keyword_match_score", 0))
    c2.metric("Semantic Match", ats.get("semantic_match_score", 0))
    c3.metric("Experience Match", ats.get("experience_match_score", 0))
    c4.metric("Education Match", ats.get("education_match_score", 0))
    c5.metric("Formatting", ats.get("formatting_score", 0))

    st.divider()

    c6, c7 = st.columns(2)

    with c6:
        st.markdown("#### ✅ Matched Keywords")
        matched = _safe_list(ats.get("matched_keywords"))
        if matched:
            st.text_area(
                "Matched Keywords",
                value="\n".join(matched),
                height=160,
                key="ats_matched_keywords",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No matched keywords found yet.")

        st.markdown("#### 💪 Strengths")
        strengths = _safe_list(ats.get("strengths"))
        if strengths:
            st.text_area(
                "Strengths",
                value="\n".join(strengths),
                height=180,
                key="ats_strengths",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No strengths returned.")

    with c7:
        st.markdown("#### ❌ Missing Keywords")
        missing = _safe_list(ats.get("missing_keywords"))
        if missing:
            st.text_area(
                "Missing Keywords",
                value="\n".join(missing),
                height=160,
                key="ats_missing_keywords",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No missing keywords returned.")

        st.markdown("#### ⚠️ Weaknesses")
        weaknesses = _safe_list(ats.get("weaknesses"))
        if weaknesses:
            st.text_area(
                "Weaknesses",
                value="\n".join(weaknesses),
                height=180,
                key="ats_weaknesses",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No weaknesses returned.")

    st.markdown("#### 🛠 Rewrite Suggestions")
    suggestions = _safe_list(ats.get("rewrite_suggestions"))
    if suggestions:
        st.text_area(
            "Rewrite Suggestions",
            value="\n".join(suggestions),
            height=180,
            key="ats_rewrite_suggestions",
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.info("No rewrite suggestions returned.")

    st.markdown("#### ✍️ Rewritten Summary Suggestion")
    rewritten_summary = str(ats.get("rewritten_summary", "") or "").strip()
    if rewritten_summary:
        st.text_area(
            "Rewritten Summary",
            value=rewritten_summary,
            height=140,
            key="ats_rewritten_summary",
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.info("No rewritten summary returned.")

def _render_recruiter_check(result: dict):
    st.subheader("👔 Senior Recruiter Check")

    match_score = int(result.get("match_score", 0))
    recruiter_summary = str(result.get("recruiter_summary", "") or "").strip()

    st.markdown(
        f"""
        <div style="
            border:1px solid #ddd;
            border-radius:12px;
            padding:18px;
            margin-bottom:12px;
        ">
            <div style="font-size:15px; color:#666;">Recruiter Match Score</div>
            <div style="font-size:42px; font-weight:700; color:{_score_color(match_score)};">{match_score}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Top 5 Missing Keywords")
        missing_keywords = _safe_list(result.get("top_5_missing_keywords"))
        if missing_keywords:
            st.text_area(
                "Recruiter Missing Keywords",
                value="\n".join(missing_keywords),
                height=180,
                key="recruiter_missing_keywords",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No missing keywords returned.")

        st.markdown("#### Top Strengths")
        strengths = _safe_list(result.get("top_strengths"))
        if strengths:
            st.text_area(
                "Recruiter Strengths",
                value="\n".join(strengths),
                height=180,
                key="recruiter_top_strengths",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No strengths returned.")

    with c2:
        st.markdown("#### Main Concerns")
        concerns = _safe_list(result.get("main_concerns"))
        if concerns:
            st.text_area(
                "Recruiter Main Concerns",
                value="\n".join(concerns),
                height=180,
                key="recruiter_main_concerns",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No concerns returned.")

        st.markdown("#### Recruiter Summary")
        if recruiter_summary:
            st.text_area(
                "Recruiter Summary",
                value=recruiter_summary,
                height=180,
                key="recruiter_summary",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No recruiter summary returned.")

def _render_readability_check(result: dict):
    st.subheader("🤖 Easy to Read")

    readability_score = int(result.get("easy_to_read_score", 0))
    summary = str(result.get("overall_readability_summary", "") or "").strip()

    st.markdown(
        f"""
        <div style="
            border:1px solid #ddd;
            border-radius:12px;
            padding:18px;
            margin-bottom:12px;
        ">
            <div style="font-size:15px; color:#666;">ATS Readability Score</div>
            <div style="font-size:42px; font-weight:700; color:{_score_color(readability_score)};">{readability_score}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Sections a Bot May Struggle With")
        problem_sections = _safe_list(result.get("sections_bot_would_struggle"))
        if problem_sections:
            st.text_area(
                "Problem Sections",
                value="\n".join(problem_sections),
                height=180,
                key="readability_problem_sections",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No problem sections returned.")

        st.markdown("#### Formatting Issues")
        issues = _safe_list(result.get("formatting_issues"))
        if issues:
            st.text_area(
                "Readability Issues",
                value="\n".join(issues),
                height=180,
                key="readability_issues",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No issues returned.")

    with c2:
        st.markdown("#### ATS Readability Fixes")
        suggestions = _safe_list(result.get("ats_readability_fixes"))
        if suggestions:
            st.text_area(
                "Readability Suggestions",
                value="\n".join(suggestions),
                height=180,
                key="readability_suggestions",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No suggestions returned.")

        st.markdown("#### Overall Readability Summary")
        if summary:
            st.text_area(
                "Readability Summary",
                value=summary,
                height=180,
                key="readability_summary",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No readability summary returned.")

def page_cv():
    st.header("📄 Generate CV")

    token = st.session_state.token
    profile = st.session_state.get("profile") or {}

    # keep local state containers ready
    if "jd_highlights" not in st.session_state:
        st.session_state["jd_highlights"] = {}
    if "ats_score_result" not in st.session_state:
        st.session_state["ats_score_result"] = {}
    if "recruiter_check_result" not in st.session_state:
        st.session_state["recruiter_check_result"] = {}
    if "easy_read_result" not in st.session_state:
        st.session_state["easy_read_result"] = {}

    # =========================================================
    # Generate new CV
    # =========================================================
    with st.expander("Generate new CV", expanded=True):
        company = st.text_input("Company", value="", key="cv_gen_company")
        job_title = st.text_input("Job Title", value="", key="cv_gen_job_title")
        model = st.text_input("Model", value="llama3.1", key="cv_gen_model")
        jd = st.text_area("Job Description *", height=220, key="cv_gen_jd")

        g1, g2 = st.columns(2)

        with g1:
            if st.button("Highlight Job Description", key="btn_highlight_jd", use_container_width=True):
                try:
                    resp = generate_jd_highlights(token, company, job_title, jd, model=model)
                    st.session_state["jd_highlights"] = resp.get("highlights") or {}
                    st.success("Job description highlights ready ✅")
                except Exception as e:
                    st.error(str(e))

        with g2:
            if st.button("Generate CV", key="btn_generate_cv", use_container_width=True):
                try:
                    resp = generate_cv(token, company, job_title, jd, model=model)
                    st.session_state.selected_draft_id = resp["draft_id"]
                    st.session_state.last_cv = resp["cv"]
                    st.session_state["ats_score_result"] = {}
                    st.session_state["recruiter_check_result"] = {}
                    st.session_state["easy_read_result"] = {}
                    st.session_state["_draft_meta"] = {
                        "company": company,
                        "job_title": job_title,
                        "job_description": jd,
                        "draft_name": resp.get("draft_name", ""),
                    }
                    st.success(f"Generated ✅ {resp.get('draft_name', resp['draft_id'])}")
                except Exception as e:
                    st.error(str(e))

    jd_highlights = _safe_dict(st.session_state.get("jd_highlights") or {})
    if jd_highlights:
        st.divider()
        _render_jd_highlights(jd_highlights)

    st.divider()

    # =========================================================
    # Drafts
    # =========================================================
    st.subheader("📌 Drafts")

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Refresh drafts", key="btn_refresh_drafts"):
            try:
                st.session_state["_drafts"] = list_drafts(token)
            except Exception as e:
                st.error(str(e))

    drafts = st.session_state.get("_drafts") or []

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
        "Select draft",
        options,
        index=selected_index,
        key="cv_selected_draft",
    )

    if selected:
        st.session_state.selected_draft_id = draft_map[selected]

        if st.button("Load draft", key="btn_load_draft"):
            try:
                d = get_draft(token, st.session_state.selected_draft_id)
                st.session_state.last_cv = d.get("cv") or {}
                st.session_state["ats_score_result"] = d.get("ats_score_result") or {}
                st.session_state["recruiter_check_result"] = d.get("recruiter_check_result") or {}
                st.session_state["easy_read_result"] = d.get("easy_read_result") or {}
                st.session_state["_draft_meta"] = {
                    "company": d.get("company", ""),
                    "job_title": d.get("job_title", ""),
                    "job_description": d.get("job_description", ""),
                    "draft_name": d.get("draft_name", ""),
                }
                st.success("Loaded ✅")
            except Exception as e:
                st.error(str(e))

    cv_obj = _safe_dict(st.session_state.get("last_cv") or {})
    meta = _safe_dict(st.session_state.get("_draft_meta") or {})
    header = _safe_dict(cv_obj.get("header"))

    # =========================================================
    # Friendly CV Editor
    # =========================================================
    st.divider()
    st.subheader("✏️ Edit CV")

    if not cv_obj:
        st.info("Generate or load a draft first.")
    else:
        edited_cv = dict(cv_obj)

        # -------------------------
        # Header
        # -------------------------
        _box("Header")

        col1, col2 = st.columns(2)
        with col1:
            edited_name = st.text_input("Name", value=header.get("name", ""), key="edit_header_name")
            edited_title = st.text_input("Professional Title", value=header.get("title", ""), key="edit_header_title")
            edited_email = st.text_input("Email", value=header.get("email", ""), key="edit_header_email")
            edited_phone = st.text_input("Phone", value=header.get("phone", ""), key="edit_header_phone")
        with col2:
            edited_location = st.text_input("Location / Address", value=header.get("location", ""), key="edit_header_location")
            edited_linkedin = st.text_input("LinkedIn", value=header.get("linkedin", ""), key="edit_header_linkedin")
            edited_github = st.text_input("GitHub", value=header.get("github", ""), key="edit_header_github")
            edited_portfolio = st.text_input("Portfolio", value=header.get("portfolio", ""), key="edit_header_portfolio")

        edited_cv["header"] = {
            "name": edited_name,
            "title": edited_title,
            "email": edited_email,
            "phone": edited_phone,
            "location": edited_location,
            "linkedin": edited_linkedin,
            "github": edited_github,
            "portfolio": edited_portfolio,
        }

        st.divider()

        # -------------------------
        # Professional Summary
        # -------------------------
        _box("Professional Summary")
        _master_reference_note(profile.get("highlights", "") or profile.get("expertise", ""))

        edited_summary = st.text_area(
            "Generated recommendation (editable)",
            value=edited_cv.get("summary", ""),
            height=140,
            key="edit_summary",
        )
        edited_cv["summary"] = edited_summary

        st.divider()

        # -------------------------
        # Areas of Expertise
        # -------------------------
        _box("Areas of Expertise")
        _master_reference_note(profile.get("expertise", ""))

        existing_areas = edited_cv.get("areas_of_expertise", [])
        edited_expertise = st.text_area(
            "Areas of Expertise (max 5, one per line or comma separated)",
            value=_join_lines(existing_areas) if isinstance(existing_areas, list) else str(existing_areas),
            height=110,
            key="edit_areas_of_expertise",
        )
        edited_cv["areas_of_expertise"] = _split_comma_or_lines(edited_expertise)[:5]

        st.divider()

        # -------------------------
        # Skills
        # -------------------------
        _box("Skills")
        _master_reference_note(profile.get("skills", ""))

        skills_dict = _safe_dict(edited_cv.get("skills"))
        edited_skills = {}

        skill_categories = [
            "Programming and Data",
            "Machine Learning and AI",
            "Data Engineering and Cloud",
            "Data Processing",
            "Automation",
            "Tools and Libraries",
            "Soft Skills",
            "Domain Strengths",
        ]

        for cat in skill_categories:
            val = skills_dict.get(cat, [])
            text_val = ", ".join(val) if isinstance(val, list) else str(val)
            edited_text = st.text_area(
                f"{cat}",
                value=text_val,
                height=68,
                key=f"skills_{cat}",
            )
            edited_skills[cat] = [x.strip() for x in edited_text.split(",") if x.strip()]

        edited_cv["skills"] = edited_skills

        st.divider()

        # -------------------------
        # Work Experience
        # -------------------------
        _box("Work Experience")
        st.caption("Using your saved master profile as reference.")

        edited_experience = []
        for i, ex in enumerate(_safe_list(edited_cv.get("experience"))):
            ex = _safe_dict(ex)
            st.markdown(f"#### Experience {i+1}")

            c1, c2 = st.columns(2)
            with c1:
                role = st.text_input("Role", value=ex.get("role", ""), key=f"exp_role_{i}")
                company_name = st.text_input("Company", value=ex.get("company", ""), key=f"exp_company_{i}")

            with c2:
                start_val = ex.get("start", "")
                end_val = ex.get("end", "")

                if not start_val and not end_val and ex.get("dates"):
                    raw_dates = str(ex.get("dates") or "")
                    if "–" in raw_dates:
                        parts = [p.strip() for p in raw_dates.split("–", 1)]
                        start_val = parts[0] if len(parts) > 0 else ""
                        end_val = parts[1] if len(parts) > 1 else ""
                    elif "-" in raw_dates:
                        parts = [p.strip() for p in raw_dates.split("-", 1)]
                        start_val = parts[0] if len(parts) > 0 else ""
                        end_val = parts[1] if len(parts) > 1 else ""

                start_date = st.text_input("Start Date", value=start_val, key=f"exp_start_{i}")
                end_date = st.text_input("End Date", value=end_val, key=f"exp_end_{i}")

            bullets = st.text_area(
                "Bullets (one per line)",
                value=_join_lines(ex.get("bullets", [])),
                height=120,
                key=f"exp_bullets_{i}",
            )

            edited_experience.append(
            {
                "role": role,
                "company": company_name,
                "start": start_date,
                "end": end_date,
                "dates": f"{start_date} – {end_date}".strip(" –"),
                "bullets": _split_lines(bullets),
            }
        )

        edited_cv["experience"] = edited_experience

        st.divider()

        # -------------------------
        # Projects
        # -------------------------
        _box("Projects")
        st.caption("Using your saved master profile as reference.")

        edited_projects = []
        for i, pr in enumerate(_safe_list(edited_cv.get("projects"))):
            pr = _safe_dict(pr)
            st.markdown(f"#### Project {i+1}")

            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Project Name", value=pr.get("name", ""), key=f"proj_name_{i}")
                tech = st.text_input("Tech", value=pr.get("tech", ""), key=f"proj_tech_{i}")

            with c2:
                start_val = pr.get("start", "")
                end_val = pr.get("end", "")

                if not start_val and not end_val and pr.get("dates"):
                    raw_dates = str(pr.get("dates") or "")
                    if "–" in raw_dates:
                        parts = [p.strip() for p in raw_dates.split("–", 1)]
                        start_val = parts[0] if len(parts) > 0 else ""
                        end_val = parts[1] if len(parts) > 1 else ""
                    elif "-" in raw_dates:
                        parts = [p.strip() for p in raw_dates.split("-", 1)]
                        start_val = parts[0] if len(parts) > 0 else ""
                        end_val = parts[1] if len(parts) > 1 else ""

                project_start = st.text_input("Start Date", value=start_val, key=f"proj_start_{i}")
                project_end = st.text_input("End Date", value=end_val, key=f"proj_end_{i}")

            bullets = st.text_area(
                "Bullets (one per line)",
                value=_join_lines(pr.get("bullets", [])),
                height=100,
                key=f"proj_bullets_{i}",
            )

            edited_projects.append(
                {
                    "name": name,
                    "tech": tech,
                    "start": project_start,
                    "end": project_end,
                    "dates": f"{project_start} – {project_end}".strip(" –"),
                    "bullets": _split_lines(bullets),
                }
            )

        edited_cv["projects"] = edited_projects

        st.divider()

        # -------------------------
        # Education
        # -------------------------
        _box("Education")
        st.caption("Using your saved master profile as reference.")

        edited_education = []
        for i, ed in enumerate(_safe_list(edited_cv.get("education"))):
            ed = _safe_dict(ed)
            st.markdown(f"#### Education {i+1}")

            degree = st.text_input("Degree", value=ed.get("degree", ""), key=f"edu_degree_{i}")
            university = st.text_input("University", value=ed.get("university", ""), key=f"edu_university_{i}")

            c1, c2 = st.columns(2)
            with c1:
                city = st.text_input("City", value=ed.get("city", ""), key=f"edu_city_{i}")
                start = st.text_input("Start", value=ed.get("start", ""), key=f"edu_start_{i}")
            with c2:
                country = st.text_input("Country", value=ed.get("country", ""), key=f"edu_country_{i}")
                end = st.text_input("End", value=ed.get("end", ""), key=f"edu_end_{i}")

            coursework = st.text_area(
                "Coursework",
                value=ed.get("coursework", ""),
                height=80,
                key=f"edu_coursework_{i}",
            )
            honors = st.text_input("Honors", value=ed.get("honors", ""), key=f"edu_honors_{i}")

            edited_education.append(
                {
                    "degree": degree,
                    "university": university,
                    "city": city,
                    "country": country,
                    "start": start,
                    "end": end,
                    "coursework": coursework,
                    "honors": honors,
                }
            )

        edited_cv["education"] = edited_education

        st.divider()

        # -------------------------
        # Certifications
        # -------------------------
        _box("Certifications")
        st.caption("Using your saved master profile as reference.")

        edited_certs = []
        certs_value = _safe_list(edited_cv.get("certifications"))

        for i, cert in enumerate(certs_value):
            st.markdown(f"#### Certification {i+1}")

            if isinstance(cert, dict):
                title = st.text_input("Title", value=cert.get("title", ""), key=f"cert_title_{i}")
                issuer = st.text_input("Issuer", value=cert.get("issuer", ""), key=f"cert_issuer_{i}")
                dates = st.text_input("Dates", value=cert.get("dates", ""), key=f"cert_dates_{i}")
                edited_certs.append(
                    {
                        "title": title,
                        "issuer": issuer,
                        "dates": dates,
                    }
                )
            else:
                line = st.text_input("Certification", value=str(cert), key=f"cert_line_{i}")
                edited_certs.append(line)

        edited_cv["certifications"] = edited_certs

        st.divider()

        # -------------------------
        # Internships
        # -------------------------
        _box("Internships")
        st.caption("Using your saved master profile as reference.")

        edited_internships = []
        for i, it in enumerate(_safe_list(edited_cv.get("internships"))):
            it = _safe_dict(it)
            st.markdown(f"#### Internship {i+1}")

            c1, c2 = st.columns(2)
            with c1:
                role = st.text_input("Role", value=it.get("role", ""), key=f"intern_role_{i}")
                company_name = st.text_input("Company", value=it.get("company", ""), key=f"intern_company_{i}")
            with c2:
                dates = st.text_input("Dates", value=it.get("dates", ""), key=f"intern_dates_{i}")

            bullets = st.text_area(
                "Bullets (one per line)",
                value=_join_lines(it.get("bullets", [])),
                height=100,
                key=f"intern_bullets_{i}",
            )

            edited_internships.append(
                {
                    "role": role,
                    "company": company_name,
                    "dates": dates,
                    "bullets": _split_lines(bullets),
                }
            )

        edited_cv["internships"] = edited_internships
        st.session_state["_edited_cv_structured"] = edited_cv

        # -------------------------
        # Actions
        # -------------------------
        st.divider()
        c3, c4, c5, c6, c7, c8 = st.columns(6)

        with c3:
            if st.button("Save edited CV", key="btn_save_structured_cv"):
                try:
                    if not st.session_state.get("selected_draft_id"):
                        st.error("Select a draft first.")
                    else:
                        save_cv_edited(token, st.session_state.selected_draft_id, edited_cv)
                        st.session_state.last_cv = edited_cv
                        st.success("Saved ✅")
                except Exception as e:
                    st.error(str(e))

        with c4:
            if st.button("Check ATS Score", key="btn_check_ats_score"):
                try:
                    if not st.session_state.get("selected_draft_id"):
                        st.error("Select a draft first.")
                    else:
                        save_cv_edited(token, st.session_state.selected_draft_id, edited_cv)
                        st.session_state.last_cv = edited_cv

                        ats_resp = score_ats(
                            token,
                            st.session_state.selected_draft_id,
                            model=st.session_state.get("cv_gen_model", "llama3.1"),
                        )
                        st.session_state["ats_score_result"] = ats_resp.get("ats_score") or {}
                        st.success("ATS score ready ✅")
                except Exception as e:
                    st.error(str(e))

        with c5:
            if st.button("Export CV DOCX", key="btn_export_cv_docx"):
                try:
                    if not st.session_state.get("selected_draft_id"):
                        st.error("Select a draft first.")
                    else:
                        resp = export_cv_docx(token, st.session_state.selected_draft_id)
                        st.success(f"DOCX ready ✅ {resp.get('filename', '')}")
                        st.code(resp.get("file_path", ""))
                except Exception as e:
                    st.error(str(e))

        with c6:
            if st.button("Export CV PDF", key="btn_export_cv_pdf"):
                try:
                    if not st.session_state.get("selected_draft_id"):
                        st.error("Select a draft first.")
                    else:
                        resp = export_cv_pdf(token, st.session_state.selected_draft_id)
                        st.success(f"PDF ready ✅ {resp.get('filename', '')}")
                        st.code(resp.get("file_path", ""))
                except Exception as e:
                    st.error(str(e))
        
        with c7:
            if st.button("Senior Recruiter Check", key="btn_recruiter_check"):
                try:
                    if not st.session_state.get("selected_draft_id"):
                        st.error("Select a draft first.")
                    else:
                        save_cv_edited(token, st.session_state.selected_draft_id, edited_cv)
                        st.session_state.last_cv = edited_cv

                        recruiter_resp = recruiter_check(
                            token,
                            st.session_state.selected_draft_id,
                            model=st.session_state.get("cv_gen_model", "llama3.1"),
                        )
                        st.session_state["recruiter_check_result"] = recruiter_resp.get("recruiter_check") or {}
                        st.success("Senior recruiter check ready ✅")
                except Exception as e:
                    st.error(str(e))

        with c8:
            if st.button("Easy to Read", key="btn_easy_read_check"):
                try:
                    if not st.session_state.get("selected_draft_id"):
                        st.error("Select a draft first.")
                    else:
                        save_cv_edited(token, st.session_state.selected_draft_id, edited_cv)
                        st.session_state.last_cv = edited_cv

                        easy_read_resp = readability_check(
                            token,
                            st.session_state.selected_draft_id,
                            model=st.session_state.get("cv_gen_model", "llama3.1"),
                        )
                        st.session_state["easy_read_result"] = easy_read_resp.get("easy_read_check") or {}
                        st.success("Easy-to-read check ready ✅")
                except Exception as e:
                    st.error(str(e))

        ats_score_result = _safe_dict(st.session_state.get("ats_score_result") or {})
        if ats_score_result:
            st.divider()
            _render_ats_score(ats_score_result)

        recruiter_result = _safe_dict(st.session_state.get("recruiter_check_result") or {})
        if recruiter_result:
            st.divider()
            _render_recruiter_check(recruiter_result)

        easy_read_result = _safe_dict(st.session_state.get("easy_read_result") or {})
        if easy_read_result:
            st.divider()
            _render_readability_check(easy_read_result)

    # =========================================================
    # Add to Tracker
    # =========================================================
    st.divider()
    st.subheader("📌 Add to Tracker")

    try:
        meta_resp = tracker_meta(token)
        statuses = meta_resp.get("statuses", ["Applied"])
        job_types = meta_resp.get("job_types", ["Full-time"])
    except Exception:
        statuses = ["Applied"]
        job_types = ["Full-time"]

    t_company = st.text_input("Company * (tracker)", value=meta.get("company", ""), key="tracker_company")
    t_role = st.text_input("Role * (tracker)", value=meta.get("job_title", ""), key="tracker_role")
    t_job_link = st.text_input("Job Link", value="", key="tracker_job_link")
    t_location = st.text_input("Location", value="", key="tracker_location")
    t_source = st.text_input("Source", value="AutoCV", key="tracker_source")
    t_job_type = st.selectbox("Job type", job_types, index=0, key="tracker_job_type")
    t_status = st.selectbox(
        "Status",
        statuses,
        index=statuses.index("Applied") if "Applied" in statuses else 0,
        key="tracker_status",
    )
    t_followup = st.number_input("Follow up in (days)", min_value=1, max_value=60, value=7, key="tracker_followup")
    t_notes = st.text_area("Notes", value="", key="tracker_notes")

    c7, c8 = st.columns(2)
    with c7:
        if st.button("Duplicate alarm (company)", key="btn_duplicate_alarm"):
            try:
                alarm = tracker_duplicate_check(token, t_company, limit=50)
                hits = alarm.get("matches") or alarm.get("history") or alarm.get("rows") or []
                if hits:
                    st.warning("Duplicate found ⚠️")
                    st.json(hits[:10])
                else:
                    st.success("No duplicates ✅")
            except Exception as e:
                st.error(str(e))

    with c8:
        if st.button("Add to Tracker ✅", key="btn_add_to_tracker"):
            try:
                payload = {
                    "company": t_company,
                    "role": t_role,
                    "job_link": t_job_link,
                    "location": t_location,
                    "source": t_source,
                    "job_type": t_job_type,
                    "status": t_status,
                    "followup_in_days": int(t_followup),
                    "notes": t_notes,
                }
                resp = tracker_add_from_draft(token, payload)
                st.success("Added ✅")
                st.json(resp)
            except Exception as e:
                st.error(str(e))