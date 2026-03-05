JD_EXTRACT_PROMPT = """
Extract structured information from this job description.

Return ONLY JSON.

{
 "role_title":"",
 "must_have_skills":[],
 "nice_to_have_skills":[],
 "responsibilities":[],
 "keywords":[]
}

Job description:
{job_description}
"""

CV_GENERATE_PROMPT = """
You are a professional resume writer.

RULES:
- Do NOT invent experience.
- Use ONLY information from the master profile.
- Select 2–3 MOST relevant experiences.
- Select top 3 MOST relevant projects.
- Summary <= 200 words.
- Bullet points must follow STAR method.
- Important skills/tools must be **bold**.

Return valid JSON.

MASTER PROFILE:
{profile}

JOB REQUIREMENTS:
{requirements}
"""