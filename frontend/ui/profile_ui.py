# frontend/ui/profile_ui.py
import json
import streamlit as st
from services.api_client import get_profile, save_profile


def _safe_list(x):
    return x if isinstance(x, list) else []


def _safe_dict(x):
    return x if isinstance(x, dict) else {}


def _skills_to_text(skills):
    if isinstance(skills, str):
        return skills
    if isinstance(skills, dict):
        parts = []
        for k, v in skills.items():
            if isinstance(v, list) and v:
                parts.append(f"{k}: {', '.join(str(i).strip() for i in v if str(i).strip())}")
            elif isinstance(v, str) and v.strip():
                parts.append(f"{k}: {v.strip()}")
        return "\n".join(parts)
    return ""


def _text_to_skill_dict(text: str):
    raw = (text or "").strip()
    if not raw:
        return ""

    out = {}
    parsed_any = False

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            key = k.strip()
            vals = [x.strip() for x in v.split(",") if x.strip()]
            if key:
                out[key] = vals
                parsed_any = True

    return out if parsed_any else raw


def _init_profile_state():
    if "profile_loaded_once" not in st.session_state:
        st.session_state.profile_loaded_once = False

    if "exp_count" not in st.session_state:
        st.session_state.exp_count = 1
    if "proj_count" not in st.session_state:
        st.session_state.proj_count = 1
    if "edu_count" not in st.session_state:
        st.session_state.edu_count = 1
    if "cert_count" not in st.session_state:
        st.session_state.cert_count = 1
    if "intern_count" not in st.session_state:
        st.session_state.intern_count = 1


def _set_if_missing(key: str, value):
    if key not in st.session_state:
        st.session_state[key] = value


def _clear_project_keys(idx: int):
    for k in [
        f"project_name_{idx}",
        f"project_desc_{idx}",
        f"project_tech_{idx}",
        f"project_start_{idx}",
        f"project_end_{idx}",
    ]:
        st.session_state.pop(k, None)


def _clear_experience_keys(idx: int):
    for k in [f"exp_role_{idx}", f"exp_company_{idx}", f"exp_start_{idx}", f"exp_end_{idx}", f"exp_desc_{idx}"]:
        st.session_state.pop(k, None)


def _clear_education_keys(idx: int):
    for k in [f"edu_degree_{idx}", f"edu_university_{idx}", f"edu_start_{idx}", f"edu_end_{idx}"]:
        st.session_state.pop(k, None)


def _clear_cert_keys(idx: int):
    for k in [f"cert_name_{idx}", f"cert_org_{idx}", f"cert_start_{idx}", f"cert_end_{idx}"]:
        st.session_state.pop(k, None)


def _clear_intern_keys(idx: int):
    for k in [f"intern_role_{idx}", f"intern_company_{idx}", f"intern_start_{idx}", f"intern_end_{idx}"]:
        st.session_state.pop(k, None)


def _load_profile_once(token: str):
    if st.session_state.profile_loaded_once:
        return

    loaded = _safe_dict(st.session_state.get("profile", {}))

    if not loaded:
        try:
            resp = get_profile(token) or {}
            loaded = _safe_dict(resp.get("profile", {}) or {})
        except Exception:
            loaded = {}

    st.session_state.loaded_profile = loaded
    st.session_state.profile = loaded

    # support top-level + nested old structures
    header = _safe_dict(loaded.get("header"))
    base = _safe_dict(loaded.get("base"))

    name_val = loaded.get("name") or header.get("name") or base.get("name") or ""
    title_val = loaded.get("title") or header.get("title") or base.get("title") or ""
    location_val = loaded.get("location") or header.get("location") or base.get("location") or ""
    email_val = loaded.get("email") or header.get("email") or base.get("email") or ""
    phone_val = loaded.get("phone") or header.get("phone") or base.get("phone") or ""
    linkedin_val = loaded.get("linkedin") or header.get("linkedin") or ""
    github_val = loaded.get("github") or header.get("github") or ""

    _set_if_missing("basic_name", name_val)
    _set_if_missing("basic_title", title_val)
    _set_if_missing("basic_location", location_val)
    _set_if_missing("basic_email", email_val)
    _set_if_missing("basic_phone", phone_val)
    _set_if_missing("basic_linkedin", linkedin_val)
    _set_if_missing("basic_github", github_val)

    _set_if_missing("expertise", loaded.get("expertise", ""))
    _set_if_missing("skills", _skills_to_text(loaded.get("skills", "")))

    loaded_projects = _safe_list(loaded.get("projects"))
    loaded_experience = _safe_list(loaded.get("experience"))
    loaded_education = _safe_list(loaded.get("education"))
    loaded_certifications = _safe_list(loaded.get("certifications"))
    loaded_internships = _safe_list(loaded.get("internships"))

    st.session_state.proj_count = max(1, len(loaded_projects))
    st.session_state.exp_count = max(1, len(loaded_experience))
    st.session_state.edu_count = max(1, len(loaded_education))
    st.session_state.cert_count = max(1, len(loaded_certifications))
    st.session_state.intern_count = max(1, len(loaded_internships))

    for i, item in enumerate(loaded_projects):
        item = _safe_dict(item)
        _set_if_missing(f"project_name_{i}", item.get("name", ""))
        _set_if_missing(f"project_desc_{i}", item.get("description", ""))
        _set_if_missing(f"project_tech_{i}", item.get("tech", ""))
        _set_if_missing(f"project_start_{i}", item.get("start", ""))
        _set_if_missing(f"project_end_{i}", item.get("end", ""))

    for i, item in enumerate(loaded_experience):
        item = _safe_dict(item)
        _set_if_missing(f"exp_role_{i}", item.get("role", ""))
        _set_if_missing(f"exp_company_{i}", item.get("company", ""))
        _set_if_missing(f"exp_start_{i}", item.get("start", ""))
        _set_if_missing(f"exp_end_{i}", item.get("end", ""))
        _set_if_missing(f"exp_desc_{i}", item.get("description", ""))

    for i, item in enumerate(loaded_education):
        item = _safe_dict(item)
        _set_if_missing(f"edu_degree_{i}", item.get("degree", ""))
        _set_if_missing(f"edu_university_{i}", item.get("university", ""))
        _set_if_missing(f"edu_start_{i}", item.get("start", ""))
        _set_if_missing(f"edu_end_{i}", item.get("end", ""))

    for i, item in enumerate(loaded_certifications):
        item = _safe_dict(item)
        _set_if_missing(f"cert_name_{i}", item.get("name", "") or item.get("title", ""))
        _set_if_missing(f"cert_org_{i}", item.get("issuer", ""))

        cert_start = item.get("start", "")
        cert_end = item.get("end", "")

        if not cert_start and not cert_end and item.get("dates"):
            raw_dates = str(item.get("dates") or "")
            if "–" in raw_dates:
                parts = [p.strip() for p in raw_dates.split("–", 1)]
                cert_start = parts[0] if len(parts) > 0 else ""
                cert_end = parts[1] if len(parts) > 1 else ""
            elif "-" in raw_dates:
                parts = [p.strip() for p in raw_dates.split("-", 1)]
                cert_start = parts[0] if len(parts) > 0 else ""
                cert_end = parts[1] if len(parts) > 1 else ""

        _set_if_missing(f"cert_start_{i}", cert_start)
        _set_if_missing(f"cert_end_{i}", cert_end)

    for i, item in enumerate(loaded_internships):
        item = _safe_dict(item)
        _set_if_missing(f"intern_role_{i}", item.get("role", ""))
        _set_if_missing(f"intern_company_{i}", item.get("company", ""))

        intern_start = item.get("start", "")
        intern_end = item.get("end", "")

        if not intern_start and not intern_end and item.get("dates"):
            raw_dates = str(item.get("dates") or "")
            if "–" in raw_dates:
                parts = [p.strip() for p in raw_dates.split("–", 1)]
                intern_start = parts[0] if len(parts) > 0 else ""
                intern_end = parts[1] if len(parts) > 1 else ""
            elif "-" in raw_dates:
                parts = [p.strip() for p in raw_dates.split("-", 1)]
                intern_start = parts[0] if len(parts) > 0 else ""
                intern_end = parts[1] if len(parts) > 1 else ""

        _set_if_missing(f"intern_start_{i}", intern_start)
        _set_if_missing(f"intern_end_{i}", intern_end)

    st.session_state.profile_loaded_once = True
def _clear_profile_form_keys():
    basic_keys = [
        "basic_name",
        "basic_title",
        "basic_location",
        "basic_email",
        "basic_phone",
        "basic_linkedin",
        "basic_github",
        "expertise",
        "skills",
    ]

    for k in basic_keys:
        st.session_state.pop(k, None)

    for i in range(st.session_state.get("proj_count", 1)):
        _clear_project_keys(i)

    for i in range(st.session_state.get("exp_count", 1)):
        _clear_experience_keys(i)

    for i in range(st.session_state.get("edu_count", 1)):
        _clear_education_keys(i)

    for i in range(st.session_state.get("cert_count", 1)):
        _clear_cert_keys(i)

    for i in range(st.session_state.get("intern_count", 1)):
        _clear_intern_keys(i)

    st.session_state.pop("proj_count", None)
    st.session_state.pop("exp_count", None)
    st.session_state.pop("edu_count", None)
    st.session_state.pop("cert_count", None)
    st.session_state.pop("intern_count", None)

def page_profile():
    _init_profile_state()
    token = st.session_state.token
    _load_profile_once(token)

    loaded = _safe_dict(st.session_state.get("loaded_profile", {}))

    st.title("Master Profile")
    st.caption("This profile is reused for CV and cover letter generation.")

    # ========================
    # Basic Info
    # ========================
    st.subheader("Basic Information")
    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input("Full Name", key="basic_name")
        title = st.text_input("Professional Title", key="basic_title")
        email = st.text_input("Email", key="basic_email")
        phone = st.text_input("Phone", key="basic_phone")

    with col2:
        location = st.text_input("Location", key="basic_location")
        linkedin = st.text_input("LinkedIn", key="basic_linkedin")
        github = st.text_input("GitHub", key="basic_github")

    st.divider()

    # ========================
    # Areas of Expertise
    # ========================
    st.subheader("Areas of Expertise")
    expertise = st.text_area(
        "List your expertise (comma separated)",
        placeholder="Machine Learning, AI Systems, NLP, Data Engineering",
        key="expertise",
        height=120,
    )

    st.divider()

    # ========================
    # Key Projects
    # ========================
    st.subheader("Key Projects")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("+ Add Project", key="add_project"):
            st.session_state.proj_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Project", key="remove_project") and st.session_state.proj_count > 1:
            idx = st.session_state.proj_count - 1
            _clear_project_keys(idx)
            st.session_state.proj_count -= 1
            st.rerun()

    projects = []
    for i in range(st.session_state.proj_count):
        st.markdown(f"**Project {i+1}**")
        project_name = st.text_input("Project Name", key=f"project_name_{i}")

        col_a, col_b = st.columns(2)
        with col_a:
            project_start = st.text_input("Start Date", key=f"project_start_{i}")
        with col_b:
            project_end = st.text_input("End Date", key=f"project_end_{i}")

        project_desc = st.text_area("Project Description", key=f"project_desc_{i}", height=110)
        project_tech = st.text_input("Technologies Used", key=f"project_tech_{i}")

        projects.append(
            {
                "name": project_name,
                "start": project_start,
                "end": project_end,
                "dates": f"{project_start} – {project_end}".strip(" –"),
                "description": project_desc,
                "tech": project_tech,
            }
        )
        st.divider()

    # ========================
    # Work Experience
    # ========================
    st.subheader("Work Experience")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("+ Add Experience", key="add_exp"):
            st.session_state.exp_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Experience", key="remove_exp") and st.session_state.exp_count > 1:
            idx = st.session_state.exp_count - 1
            _clear_experience_keys(idx)
            st.session_state.exp_count -= 1
            st.rerun()

    experiences = []
    for i in range(st.session_state.exp_count):
        st.markdown(f"**Experience {i+1}**")
        role = st.text_input("Role", key=f"exp_role_{i}")
        company = st.text_input("Company", key=f"exp_company_{i}")

        col_a, col_b = st.columns(2)
        with col_a:
            start = st.text_input("Start Date", key=f"exp_start_{i}")
        with col_b:
            end = st.text_input("End Date", key=f"exp_end_{i}")

        exp_desc = st.text_area("Responsibilities / Achievements", key=f"exp_desc_{i}", height=120)

        experiences.append(
            {
                "role": role,
                "company": company,
                "start": start,
                "end": end,
                "description": exp_desc,
            }
        )
        st.divider()

    # ========================
    # Education
    # ========================
    st.subheader("Education")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("+ Add Education", key="add_edu"):
            st.session_state.edu_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Education", key="remove_edu") and st.session_state.edu_count > 1:
            idx = st.session_state.edu_count - 1
            _clear_education_keys(idx)
            st.session_state.edu_count -= 1
            st.rerun()

    education_list = []
    for i in range(st.session_state.edu_count):
        st.markdown(f"**Education {i+1}**")
        degree = st.text_input("Degree", key=f"edu_degree_{i}")
        university = st.text_input("University", key=f"edu_university_{i}")

        col_a, col_b = st.columns(2)
        with col_a:
            edu_start = st.text_input("Start Date", key=f"edu_start_{i}")
        with col_b:
            edu_end = st.text_input("End Date", key=f"edu_end_{i}")

        education_list.append(
            {
                "degree": degree,
                "university": university,
                "start": edu_start,
                "end": edu_end,
            }
        )
        st.divider()

    # ========================
    # Certifications
    # ========================
    st.subheader("Professional Certifications")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("+ Add Certification", key="add_cert"):
            st.session_state.cert_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Certification", key="remove_cert") and st.session_state.cert_count > 1:
            idx = st.session_state.cert_count - 1
            _clear_cert_keys(idx)
            st.session_state.cert_count -= 1
            st.rerun()

    certifications = []
    for i in range(st.session_state.cert_count):
        st.markdown(f"**Certification {i+1}**")
        cert_name = st.text_input("Certification Name", key=f"cert_name_{i}")
        cert_org = st.text_input("Issuer", key=f"cert_org_{i}")

        col_a, col_b = st.columns(2)
        with col_a:
            cert_start = st.text_input("Start Date", key=f"cert_start_{i}")
        with col_b:
            cert_end = st.text_input("End Date", key=f"cert_end_{i}")

        certifications.append(
            {
                "name": cert_name,
                "title": cert_name,
                "issuer": cert_org,
                "start": cert_start,
                "end": cert_end,
                "dates": f"{cert_start} – {cert_end}".strip(" –"),
            }
        )
        st.divider()

    # ========================
    # Internships
    # ========================
    st.subheader("Internships")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("+ Add Internship", key="add_intern"):
            st.session_state.intern_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Internship", key="remove_intern") and st.session_state.intern_count > 1:
            idx = st.session_state.intern_count - 1
            _clear_intern_keys(idx)
            st.session_state.intern_count -= 1
            st.rerun()

    internships = []
    for i in range(st.session_state.intern_count):
        st.markdown(f"**Internship {i+1}**")
        intern_role = st.text_input("Internship Role", key=f"intern_role_{i}")
        intern_company = st.text_input("Internship Company", key=f"intern_company_{i}")

        col_a, col_b = st.columns(2)
        with col_a:
            intern_start = st.text_input("Start Date", key=f"intern_start_{i}")
        with col_b:
            intern_end = st.text_input("End Date", key=f"intern_end_{i}")

        internships.append(
            {
                "role": intern_role,
                "company": intern_company,
                "start": intern_start,
                "end": intern_end,
                "dates": f"{intern_start} – {intern_end}".strip(" –"),
            }
        )
        st.divider()

    # ========================
    # Skills
    # ========================
    st.subheader("Key Skills")
    skills = st.text_area(
        "Skills",
        placeholder="technical: Python, SQL\nml: XGBoost, PyTorch\ntools: FastAPI, Azure",
        key="skills",
        height=160,
    )

    st.divider()

    current_profile = {
        "name": name,
        "title": title,
        "location": location,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "expertise": expertise,
        "projects": projects,
        "experience": experiences,
        "education": education_list,
        "certifications": certifications,
        "internships": internships,
        "skills": _text_to_skill_dict(skills),
    }

    if json.dumps(current_profile, sort_keys=True) != json.dumps(loaded, sort_keys=True):
        st.warning("You have unsaved changes.")

    col_save, col_refresh = st.columns([1, 1])

    with col_save:
        if st.button("Save Profile", key="save_profile_btn", use_container_width=True):
            try:
                save_profile(token, current_profile)
                st.session_state.loaded_profile = current_profile
                st.session_state.profile = current_profile
                st.success("Profile saved successfully.")
            except Exception as e:
                st.error(str(e))

    with col_refresh:
        if st.button("Reload Saved Profile", key="reload_profile_btn", use_container_width=True):
            _clear_profile_form_keys()
            st.session_state.profile_loaded_once = False
            st.session_state.loaded_profile = {}
            st.session_state.profile = {}
            st.rerun()