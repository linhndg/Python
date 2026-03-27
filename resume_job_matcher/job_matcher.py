import re


def _normalize_tokens(text):
    return set(re.split(r"[^a-z0-9+#.]+", text.lower()))


def calculate_skill_score(resume_skills, job_description):
    if not resume_skills:
        return 0.0
    desc_lower = job_description.lower()
    matched = sum(1 for skill in resume_skills if skill.lower() in desc_lower)
    return matched / len(resume_skills)


def calculate_experience_score(resume_experience, job_description):
    if not resume_experience:
        return 0.1  # Small baseline score

    desc_lower = job_description.lower()
    title_score = 0
    for exp in resume_experience:
        title_words = set(exp["title"].lower().split())
        desc_words = _normalize_tokens(desc_lower)
        overlap = title_words & desc_words
        if overlap:
            title_score = max(title_score, len(overlap) / max(len(title_words), 1))

    years_score = min(len(resume_experience) * 0.25, 1.0)

    return 0.5 * title_score + 0.5 * years_score


def calculate_education_score(resume_education, job_description):
    if not resume_education:
        return 0.1

    desc_lower = job_description.lower()
    degree_levels = {"associate": 1, "bachelor": 2, "b.s.": 2, "b.a.": 2,
                     "master": 3, "m.s.": 3, "m.a.": 3, "mba": 3,
                     "ph.d.": 4, "phd": 4, "doctorate": 4}

    max_level = 0
    field_match = False
    for edu in resume_education:
        degree_lower = edu["degree"].lower().rstrip("s.'")
        for key, level in degree_levels.items():
            if key in degree_lower:
                max_level = max(max_level, level)
                break
        if edu.get("field") and edu["field"].lower() in desc_lower:
            field_match = True

    degree_score = min(max_level / 4.0, 1.0)
    field_bonus = 0.3 if field_match else 0.0

    return min(degree_score + field_bonus, 1.0)


def score_job(resume_data, job):
    skill_score = calculate_skill_score(resume_data["skills"], job["description"])
    exp_score = calculate_experience_score(resume_data["experience"], job["description"])
    edu_score = calculate_education_score(resume_data["education"], job["description"])

    return round(0.60 * skill_score + 0.25 * exp_score + 0.15 * edu_score, 4)


def rank_jobs(resume_data, jobs):
    for job in jobs:
        job["match_score"] = score_job(resume_data, job)
    return sorted(jobs, key=lambda j: j["match_score"], reverse=True)
