import requests

from config import Config
import models


def search_jobs_jsearch(query, location="", num_pages=1):
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": Config.RAPIDAPI_KEY,
        "X-RapidAPI-Host": Config.RAPIDAPI_HOST,
    }
    params = {
        "query": query,
        "page": "1",
        "num_pages": str(num_pages),
    }
    if location:
        params["query"] = f"{query} in {location}"

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except (requests.RequestException, ValueError):
        return []

    jobs = []
    for item in data:
        jobs.append({
            "title": item.get("job_title", "Unknown"),
            "company": item.get("employer_name", "Unknown"),
            "location": item.get("job_city", item.get("job_state", "Remote")),
            "description": item.get("job_description", ""),
            "url": item.get("job_apply_link", item.get("job_google_link", "#")),
            "source": "jsearch",
        })
    return jobs


def search_jobs_mock(query):
    """Return sample jobs for demo/development when no API key is set."""
    skills = [s.strip().lower() for s in query.split()]

    mock_jobs = [
        {
            "title": "Senior Python Developer",
            "company": "TechCorp Inc.",
            "location": "San Francisco, CA",
            "description": (
                "We are looking for a Senior Python Developer with experience in Django, Flask, "
                "REST APIs, PostgreSQL, Docker, and AWS. You will build scalable web applications, "
                "mentor junior developers, and participate in agile sprints. Knowledge of machine "
                "learning, data science, and CI/CD pipelines is a plus. Strong communication and "
                "problem solving skills required."
            ),
            "url": "https://example.com/jobs/senior-python-dev",
            "source": "mock",
        },
        {
            "title": "Full Stack Engineer",
            "company": "StartupXYZ",
            "location": "New York, NY",
            "description": (
                "Join our team as a Full Stack Engineer working with React, Node.js, TypeScript, "
                "PostgreSQL, and AWS. Experience with Docker, Kubernetes, CI/CD, and agile "
                "methodologies preferred. You will design and implement features, write unit tests, "
                "and collaborate with product managers. Strong JavaScript and Python skills required."
            ),
            "url": "https://example.com/jobs/fullstack-eng",
            "source": "mock",
        },
        {
            "title": "Data Scientist",
            "company": "DataDriven Co.",
            "location": "Remote",
            "description": (
                "Seeking a Data Scientist proficient in Python, R, SQL, TensorFlow, PyTorch, "
                "scikit-learn, and pandas. You will analyze large datasets, build predictive models, "
                "and create data visualizations with matplotlib and Tableau. Experience with NLP, "
                "deep learning, and cloud platforms (AWS/GCP) is highly valued. PhD preferred."
            ),
            "url": "https://example.com/jobs/data-scientist",
            "source": "mock",
        },
        {
            "title": "DevOps Engineer",
            "company": "CloudFirst Ltd.",
            "location": "Austin, TX",
            "description": (
                "Looking for a DevOps Engineer skilled in AWS, Docker, Kubernetes, Terraform, "
                "Jenkins, GitHub Actions, Linux, and Python. You will manage CI/CD pipelines, "
                "automate infrastructure, monitor systems, and ensure high availability. Experience "
                "with microservices architecture and agile teams required."
            ),
            "url": "https://example.com/jobs/devops-eng",
            "source": "mock",
        },
        {
            "title": "Machine Learning Engineer",
            "company": "AI Solutions Inc.",
            "location": "Seattle, WA",
            "description": (
                "We need a Machine Learning Engineer with strong Python, TensorFlow, PyTorch, "
                "scikit-learn, and SQL skills. Experience with NLP, computer vision, deep learning, "
                "and deploying models to production (Docker, Kubernetes, AWS). Excellent problem "
                "solving and communication skills. MS or PhD in Computer Science preferred."
            ),
            "url": "https://example.com/jobs/ml-engineer",
            "source": "mock",
        },
        {
            "title": "Backend Software Engineer",
            "company": "ScaleUp Systems",
            "location": "Chicago, IL",
            "description": (
                "Backend Software Engineer needed with expertise in Java, Python, Spring, "
                "PostgreSQL, MongoDB, Redis, Kafka, and microservices. You will design APIs, "
                "optimize database queries, and build distributed systems. Docker, Kubernetes, "
                "and CI/CD experience required. Agile team environment."
            ),
            "url": "https://example.com/jobs/backend-eng",
            "source": "mock",
        },
        {
            "title": "Frontend Developer",
            "company": "DesignTech Co.",
            "location": "Los Angeles, CA",
            "description": (
                "Frontend Developer role focusing on React, TypeScript, JavaScript, HTML, CSS, "
                "Tailwind, and Redux. Build responsive web applications, collaborate with designers "
                "using Figma, write unit tests, and optimize performance. Experience with Next.js, "
                "GraphQL, and CI/CD is a plus. Strong communication skills needed."
            ),
            "url": "https://example.com/jobs/frontend-dev",
            "source": "mock",
        },
        {
            "title": "Cloud Solutions Architect",
            "company": "Enterprise Cloud Corp.",
            "location": "Denver, CO",
            "description": (
                "Cloud Solutions Architect with deep AWS/Azure/GCP expertise. Design cloud "
                "architecture, implement Terraform/CloudFormation, manage Kubernetes clusters, "
                "and lead DevOps transformation. Strong knowledge of Python, system design, "
                "microservices, serverless, and cybersecurity best practices. Leadership and "
                "stakeholder management skills essential."
            ),
            "url": "https://example.com/jobs/cloud-architect",
            "source": "mock",
        },
    ]

    return mock_jobs


def search_jobs(skills, location=""):
    query = " ".join(skills[:5])
    if Config.RAPIDAPI_KEY:
        jobs = search_jobs_jsearch(query, location)
    else:
        jobs = search_jobs_mock(query)

    if not jobs:
        jobs = search_jobs_mock(query)

    job_ids = models.save_jobs(jobs)
    for i, job in enumerate(jobs):
        job["id"] = job_ids[i]

    return jobs
