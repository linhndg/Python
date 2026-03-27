from datetime import date


def _find_overlapping_skills(resume_skills, job_description, max_skills=5):
    desc_lower = job_description.lower()
    return [s for s in resume_skills if s.lower() in desc_lower][:max_skills]


def generate_cover_letter(resume_data, job):
    today = date.today().strftime("%B %d, %Y")
    title = job.get("title", "the open position")
    company = job.get("company", "your company")
    description = job.get("description", "")

    overlapping = _find_overlapping_skills(resume_data["skills"], description)
    skills_text = ""
    if overlapping:
        if len(overlapping) == 1:
            skills_text = overlapping[0]
        else:
            skills_text = ", ".join(overlapping[:-1]) + f", and {overlapping[-1]}"

    experience = resume_data.get("experience", [])
    exp_text = ""
    if experience:
        latest = experience[0]
        exp_text = (
            f"In my most recent role as {latest['title']} at {latest['company']}, "
            f"I developed expertise that directly aligns with this position. "
            f"With {len(experience)} role{'s' if len(experience) > 1 else ''} "
            f"in my career, I bring a depth of practical experience."
        )

    education = resume_data.get("education", [])
    edu_text = ""
    if education:
        top = education[0]
        edu_text = f"I hold a {top['degree']}"
        if top.get("field"):
            edu_text += f" in {top['field']}"
        if top.get("institution"):
            edu_text += f" from {top['institution']}"
        edu_text += ", providing a strong academic foundation for this role."

    letter = f"""{today}

Dear Hiring Manager,

I am writing to express my strong interest in the {title} position at {company}. After reviewing the job description, I am confident that my skills and experience make me an excellent candidate for this role.

"""
    if skills_text:
        letter += (
            f"I bring strong proficiency in {skills_text}, which are directly "
            f"relevant to the requirements outlined in your job posting. These "
            f"technical competencies, combined with my hands-on project experience, "
            f"enable me to contribute effectively from day one.\n\n"
        )

    if exp_text:
        letter += f"{exp_text}\n\n"

    if edu_text:
        letter += f"{edu_text}\n\n"

    letter += (
        f"I am excited about the opportunity to contribute to {company}'s mission "
        f"and would welcome the chance to discuss how my background and skills "
        f"would be a great fit for your team. I am available for an interview at "
        f"your earliest convenience.\n\n"
        f"Thank you for considering my application. I look forward to hearing from you.\n\n"
        f"Sincerely,\n"
        f"[Your Name]"
    )

    return letter
