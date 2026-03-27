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
    r"(?:Bachelor'?s?|B\.?S\.?|B\.?A\.?|B\.?Sc\.?)",
    r"(?:Master'?s?|M\.?S\.?|M\.?A\.?|M\.?Sc\.?|MBA)",
    r"(?:Ph\.?D\.?|Doctorate)",
    r"(?:Associate'?s?|A\.?S\.?|A\.?A\.?)",
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
        else:
            # Use the line before the date as the title
            if i > 0 and lines[i - 1].strip():
                title = lines[i - 1].strip()

        if title:
            experiences.append({
                "title": title[:100],
                "company": company[:100] if company else "Unknown",
                "duration": f"{date_match.group(1)} - {date_match.group(2)}",
            })

    return experiences


def extract_education(text):
    education = []
    degree_regex = "|".join(DEGREE_PATTERNS)

    for match in re.finditer(
        rf"({degree_regex})[\s,]*((?:of|in)\s+[\w\s]+)?", text, re.IGNORECASE
    ):
        degree = match.group(1).strip()
        field = match.group(2).strip("., \t") if match.group(2) else ""
        field = field.lstrip("of in ").strip() if field else ""

        # Look for institution nearby
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        context = text[start:end]
        inst_match = re.search(
            r"([\w\s]+(?:University|College|Institute|School|Academy)[\w\s]*)",
            context,
        )
        institution = inst_match.group(1).strip() if inst_match else ""

        education.append({
            "degree": degree,
            "field": field[:100],
            "institution": institution[:100],
        })

    return education


def parse_resume(file_path):
    full_text = extract_text(file_path)
    return {
        "full_text": full_text,
        "skills": extract_skills(full_text),
        "experience": extract_experience(full_text),
        "education": extract_education(full_text),
    }
