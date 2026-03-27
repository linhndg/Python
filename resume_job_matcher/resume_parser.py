import re

import pdfplumber
from docx import Document

KNOWN_SKILLS = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "ruby", "go",
    "rust", "swift", "kotlin", "php", "scala", "r", "matlab", "perl", "shell",
    "bash", "powershell", "sql", "html", "css", "sass",
    # Frameworks & libraries
    "react", "angular", "vue", "django", "flask", "fastapi", "spring",
    "express", "node.js", "next.js", "nuxt", "rails", "laravel", "asp.net",
    "bootstrap", "tailwind", "jquery", "redux", "graphql", "rest api",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "matplotlib", "opencv", "nltk", "spacy",
    # Databases
    "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "sqlite",
    "oracle", "sql server", "dynamodb", "cassandra", "neo4j", "firebase",
    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform",
    "ansible", "jenkins", "github actions", "gitlab ci", "circleci",
    "cloudformation", "heroku", "vercel", "netlify",
    # Tools & platforms
    "git", "github", "gitlab", "bitbucket", "jira", "confluence", "slack",
    "linux", "unix", "windows server", "nginx", "apache", "kafka", "rabbitmq",
    "celery", "airflow", "spark", "hadoop", "tableau", "power bi", "excel",
    "figma", "sketch", "photoshop",
    # Concepts & methodologies
    "machine learning", "deep learning", "natural language processing",
    "computer vision", "data science", "data analysis", "data engineering",
    "etl", "ci/cd", "devops", "agile", "scrum", "kanban", "microservices",
    "api design", "system design", "object oriented programming",
    "functional programming", "test driven development", "unit testing",
    "integration testing", "cybersecurity", "penetration testing",
    "cloud architecture", "serverless", "blockchain",
    # Soft skills
    "leadership", "project management", "communication", "teamwork",
    "problem solving", "critical thinking", "time management", "mentoring",
    "stakeholder management", "presentation", "technical writing",
]

DEGREE_PATTERNS = [
    r"(?:Bachelor'?s?|B\.S\.?|B\.A\.?|B\.Sc\.?)",
    r"(?:Master'?s?|M\.S\.?|M\.A\.?|M\.Sc\.?|MBA)",
    r"(?:Ph\.?D\.?|Doctorate)",
    r"(?:Associate'?s?)",
]

MONTH_PATTERN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_PATTERN = rf"(?:{MONTH_PATTERN}\s+\d{{4}}|\d{{4}})"
DATE_RANGE_PATTERN = rf"({DATE_PATTERN})\s*[-\u2013\u2014to]+\s*({DATE_PATTERN}|[Pp]resent|[Cc]urrent)"


def extract_text_from_pdf(file_path):
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(file_path):
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return extract_text_from_pdf(file_path)
    elif ext == "docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: .{ext}")


def extract_skills(text):
    text_lower = text.lower()
    found = []
    for skill in KNOWN_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return sorted(set(found))


def extract_experience(text):
    experiences = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        date_match = re.search(DATE_RANGE_PATTERN, line)
        if not date_match:
            continue

        title = ""
        company = ""

        # Look at current line and nearby lines for title/company
        context = line
        if i > 0:
            context = lines[i - 1] + " " + context

        # Try "Title at Company" pattern
        role_match = re.search(
            r"([A-Z][\w\s]+?)\s+(?:at|@|\||-|,)\s+([A-Z][\w\s&,.]+)", context
        )
        if role_match:
            title = role_match.group(1).strip()
            company = role_match.group(2).strip()
            # Remove any trailing date info from company
            company = re.split(DATE_PATTERN, company)[0].strip().rstrip(",- ")
        else:
            # Use the line before the date as the title
            if i > 0 and lines[i - 1].strip():
                title = lines[i - 1].strip()
                # Remove trailing date info
                title = re.split(DATE_PATTERN, title)[0].strip().rstrip(",- ")

        if title:
            experiences.append({
                "title": title[:100],
                "company": company[:100] if company else "Unknown",
                "duration": f"{date_match.group(1)} - {date_match.group(2)}",
            })

    return experiences


def extract_education(text):
    education = []
    normalized = " ".join(text.split())  # Collapse all whitespace

    # Find institutions - match "University of X" or "X University" patterns
    institutions = []
    # First try "University/College of X" pattern
    for m in re.finditer(
        r"((?:University|College|Institute|Academy)\s+of\s+[A-Z][\w]+(?:[,\s]+[A-Z][\w]+)*)",
        normalized,
    ):
        institutions.append((m.start(), m.group(1)))
    # Then try "X University/College" pattern
    for m in re.finditer(
        r"((?:[A-Z][a-z]+\s+){1,3}(?:University|College|Institute|School|Academy))",
        normalized,
    ):
        # Skip if overlapping with a "University of" match
        m_end = m.end()
        if not any(pos < m_end and pos + len(name) > m.start() for pos, name in institutions):
            institutions.append((m.start(), m.group(1)))

    # Match "Degree in Field" patterns - field ends at University/College/digits/punctuation
    degree_pattern = (
        r"\b(Bachelor'?s?|Master'?s?|MBA|Ph\.?D\.?|Doctorate|Associate'?s?|"
        r"B\.S\.?|B\.A\.?|M\.S\.?|M\.A\.?|B\.Sc\.?|M\.Sc\.?)"
        r"\s*(?:degree\s+)?(?:(?:of|in)\s+([\w\s,/&]+?))?"
        r"(?:\s+(?:University|College|Institute|School|from|at)\b|\s*[-,.\u2013]|\s+\d{4}|\s*$)"
    )

    for match in re.finditer(degree_pattern, normalized):
        degree = match.group(1).strip()
        field = match.group(2).strip().rstrip(",.") if match.group(2) else ""

        if len(degree) < 3:
            continue

        # Find the closest institution
        match_pos = match.start()
        institution = ""
        best_dist = float("inf")
        for inst_pos, inst_name in institutions:
            dist = abs(inst_pos - match_pos)
            if dist < best_dist:
                best_dist = dist
                institution = inst_name.strip()

        entry = {"degree": degree, "field": field[:100], "institution": institution[:100]}
        if not any(e["degree"] == entry["degree"] for e in education):
            education.append(entry)

    return education


def parse_resume(file_path):
    full_text = extract_text(file_path)
    return {
        "full_text": full_text,
        "skills": extract_skills(full_text),
        "experience": extract_experience(full_text),
        "education": extract_education(full_text),
    }
