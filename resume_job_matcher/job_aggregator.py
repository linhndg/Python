"""
Multi-source job aggregator.
Queries multiple job boards, normalizes results, deduplicates, and stores in DB.

Supported sources:
- JSearch (RapidAPI) - aggregates from LinkedIn, Indeed, Glassdoor, etc.
- Adzuna - UK/US job search API
- The Muse - curated tech jobs
- Remotive - remote tech jobs (free, no key needed)
- USAJobs - US government jobs (free, key from usajobs.gov)
- Mock data - fallback for development
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from config import Config
import models

logger = logging.getLogger(__name__)


def _safe_request(method, url, **kwargs):
    """Make an HTTP request with error handling."""
    kwargs.setdefault("timeout", 15)
    try:
        resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None


# ============================================================
# Source: JSearch (RapidAPI) - aggregates LinkedIn, Indeed, etc.
# ============================================================

def fetch_jsearch(query, location="", pages=2):
    if not Config.RAPIDAPI_KEY:
        return []

    jobs = []
    for page in range(1, pages + 1):
        q = f"{query} in {location}" if location else query
        data = _safe_request(
            "GET", "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key": Config.RAPIDAPI_KEY,
                "X-RapidAPI-Host": Config.RAPIDAPI_HOST,
            },
            params={"query": q, "page": str(page), "num_pages": "1",
                    "country": "us", "date_posted": "week"},
        )
        if not data:
            break
        for item in data.get("data", []):
            jobs.append({
                "title": item.get("job_title", ""),
                "company": item.get("employer_name", ""),
                "location": item.get("job_city", item.get("job_state", "USA")),
                "description": item.get("job_description", "")[:5000],
                "url": item.get("job_apply_link", item.get("job_google_link", "#")),
                "source": "jsearch",
                "job_type": item.get("job_employment_type", ""),
                "salary": _format_salary(item.get("job_min_salary"), item.get("job_max_salary")),
                "date_posted": item.get("job_posted_at_datetime_utc", "")[:10],
                "remote": item.get("job_is_remote", False),
            })
    return jobs


# ============================================================
# Source: Adzuna API
# ============================================================

def fetch_adzuna(query, location="", pages=2):
    if not Config.ADZUNA_APP_ID or not Config.ADZUNA_APP_KEY:
        return []

    jobs = []
    for page in range(1, pages + 1):
        where = location if location else "us"
        data = _safe_request(
            "GET", f"https://api.adzuna.com/v1/api/jobs/us/search/{page}",
            params={
                "app_id": Config.ADZUNA_APP_ID,
                "app_key": Config.ADZUNA_APP_KEY,
                "what": query,
                "where": where,
                "results_per_page": 20,
                "max_days_old": 7,
                "sort_by": "date",
            },
        )
        if not data:
            break
        for item in data.get("results", []):
            loc = item.get("location", {})
            loc_str = ", ".join(loc.get("area", [])) if loc else ""
            jobs.append({
                "title": item.get("title", ""),
                "company": item.get("company", {}).get("display_name", ""),
                "location": loc_str or "USA",
                "description": item.get("description", "")[:5000],
                "url": item.get("redirect_url", "#"),
                "source": "adzuna",
                "salary": _format_salary(item.get("salary_min"), item.get("salary_max")),
                "date_posted": item.get("created", "")[:10],
                "remote": "remote" in item.get("title", "").lower(),
            })
    return jobs


# ============================================================
# Source: Remotive API (free, no key needed - remote jobs)
# ============================================================

def fetch_remotive(query, limit=50):
    data = _safe_request(
        "GET", "https://remotive.com/api/remote-jobs",
        params={"search": query, "limit": limit},
    )
    if not data:
        return []

    jobs = []
    for item in data.get("jobs", []):
        jobs.append({
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": item.get("candidate_required_location", "Worldwide"),
            "description": _strip_html(item.get("description", ""))[:5000],
            "url": item.get("url", "#"),
            "source": "remotive",
            "job_type": item.get("job_type", ""),
            "salary": item.get("salary", ""),
            "date_posted": item.get("publication_date", "")[:10],
            "remote": True,
        })
    return jobs


# ============================================================
# Source: The Muse API (free, no key needed)
# ============================================================

def fetch_themuse(query, location="", page=0):
    params = {"page": page, "descending": "true"}
    if location:
        params["location"] = location

    data = _safe_request(
        "GET", "https://www.themuse.com/api/public/jobs",
        params=params,
    )
    if not data:
        return []

    query_lower = query.lower()
    jobs = []
    for item in data.get("results", []):
        title = item.get("name", "")
        company = item.get("company", {}).get("name", "") if item.get("company") else ""
        desc = _strip_html(item.get("contents", ""))
        # Filter by query relevance (The Muse API doesn't support keyword search well)
        if not any(kw in title.lower() or kw in desc.lower() for kw in query_lower.split()):
            continue
        locs = [l.get("name", "") for l in item.get("locations", [])]
        jobs.append({
            "title": title,
            "company": company,
            "location": ", ".join(locs) if locs else "USA",
            "description": desc[:5000],
            "url": item.get("refs", {}).get("landing_page", "#"),
            "source": "themuse",
            "job_type": item.get("type", ""),
            "date_posted": item.get("publication_date", "")[:10],
            "remote": any("remote" in l.lower() for l in locs),
        })
    return jobs


# ============================================================
# Source: USAJobs (US Government - free API key from usajobs.gov)
# ============================================================

def fetch_usajobs(query, location="", pages=1):
    if not Config.USAJOBS_API_KEY:
        return []

    jobs = []
    for page in range(1, pages + 1):
        params = {
            "Keyword": query,
            "ResultsPerPage": 25,
            "Page": page,
            "DatePosted": 7,
        }
        if location:
            params["LocationName"] = location

        data = _safe_request(
            "GET", "https://data.usajobs.gov/api/search",
            headers={
                "Authorization-Key": Config.USAJOBS_API_KEY,
                "User-Agent": Config.USAJOBS_EMAIL or "job-matcher@example.com",
            },
            params=params,
        )
        if not data:
            break

        for item in data.get("SearchResult", {}).get("SearchResultItems", []):
            pos = item.get("MatchedObjectDescriptor", {})
            loc_list = pos.get("PositionLocation", [{}])
            loc_name = loc_list[0].get("LocationName", "USA") if loc_list else "USA"
            salary = pos.get("PositionRemuneration", [{}])
            sal_str = ""
            if salary:
                sal_str = f"${salary[0].get('MinimumRange', '')}-${salary[0].get('MaximumRange', '')} {salary[0].get('RateIntervalCode', '')}"

            jobs.append({
                "title": pos.get("PositionTitle", ""),
                "company": pos.get("OrganizationName", "US Government"),
                "location": loc_name,
                "description": _strip_html(pos.get("QualificationSummary", ""))[:5000],
                "url": pos.get("PositionURI", "#"),
                "source": "usajobs",
                "job_type": pos.get("PositionSchedule", [{}])[0].get("Name", "") if pos.get("PositionSchedule") else "",
                "salary": sal_str,
                "date_posted": pos.get("PublicationStartDate", "")[:10],
                "remote": "remote" in loc_name.lower() or "telework" in str(pos).lower(),
            })
    return jobs


# ============================================================
# Mock data fallback (always works, no API key needed)
# ============================================================

def fetch_mock(query):
    """Comprehensive mock jobs for development/demo."""
    return [
        {
            "title": "Senior Python Developer",
            "company": "TechCorp Inc.",
            "location": "San Francisco, CA",
            "description": "We are looking for a Senior Python Developer with experience in Django, Flask, REST APIs, PostgreSQL, Docker, and AWS. You will build scalable web applications, mentor junior developers, and participate in agile sprints. Knowledge of machine learning, data science, and CI/CD pipelines is a plus. Strong communication and problem solving skills required.",
            "url": "https://example.com/jobs/senior-python-dev",
            "source": "mock", "job_type": "Full-time", "salary": "$140,000-$180,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
        {
            "title": "Full Stack Engineer",
            "company": "StartupXYZ",
            "location": "New York, NY",
            "description": "Join our team as a Full Stack Engineer working with React, Node.js, TypeScript, PostgreSQL, and AWS. Experience with Docker, Kubernetes, CI/CD, and agile methodologies preferred. You will design and implement features, write unit tests, and collaborate with product managers.",
            "url": "https://example.com/jobs/fullstack-eng",
            "source": "mock", "job_type": "Full-time", "salary": "$130,000-$170,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
        {
            "title": "Data Scientist",
            "company": "DataDriven Co.",
            "location": "Remote",
            "description": "Seeking a Data Scientist proficient in Python, R, SQL, TensorFlow, PyTorch, scikit-learn, and pandas. Build predictive models, create data visualizations. Experience with NLP, deep learning, and cloud platforms (AWS/GCP) is highly valued.",
            "url": "https://example.com/jobs/data-scientist",
            "source": "mock", "job_type": "Full-time", "salary": "$120,000-$160,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": True,
        },
        {
            "title": "DevOps Engineer",
            "company": "CloudFirst Ltd.",
            "location": "Austin, TX",
            "description": "Looking for a DevOps Engineer skilled in AWS, Docker, Kubernetes, Terraform, Jenkins, GitHub Actions, Linux, and Python. Manage CI/CD pipelines, automate infrastructure, monitor systems. Experience with microservices and agile teams required.",
            "url": "https://example.com/jobs/devops-eng",
            "source": "mock", "job_type": "Full-time", "salary": "$135,000-$175,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
        {
            "title": "Machine Learning Engineer",
            "company": "AI Solutions Inc.",
            "location": "Seattle, WA",
            "description": "Machine Learning Engineer with strong Python, TensorFlow, PyTorch, scikit-learn, and SQL skills. Experience with NLP, computer vision, deep learning, and deploying models to production (Docker, Kubernetes, AWS).",
            "url": "https://example.com/jobs/ml-engineer",
            "source": "mock", "job_type": "Full-time", "salary": "$150,000-$200,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
        {
            "title": "Backend Software Engineer",
            "company": "ScaleUp Systems",
            "location": "Chicago, IL",
            "description": "Backend Engineer needed with expertise in Java, Python, Spring, PostgreSQL, MongoDB, Redis, Kafka, and microservices. Design APIs, optimize database queries, build distributed systems.",
            "url": "https://example.com/jobs/backend-eng",
            "source": "mock", "job_type": "Full-time", "salary": "$125,000-$165,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
        {
            "title": "Frontend Developer",
            "company": "DesignTech Co.",
            "location": "Los Angeles, CA",
            "description": "Frontend Developer role focusing on React, TypeScript, JavaScript, HTML, CSS, Tailwind, and Redux. Build responsive web applications, collaborate with designers using Figma, write unit tests.",
            "url": "https://example.com/jobs/frontend-dev",
            "source": "mock", "job_type": "Full-time", "salary": "$115,000-$150,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
        {
            "title": "Cloud Solutions Architect",
            "company": "Enterprise Cloud Corp.",
            "location": "Denver, CO",
            "description": "Cloud Solutions Architect with deep AWS/Azure/GCP expertise. Design cloud architecture, implement Terraform/CloudFormation, manage Kubernetes clusters. Leadership and stakeholder management skills essential.",
            "url": "https://example.com/jobs/cloud-architect",
            "source": "mock", "job_type": "Full-time", "salary": "$160,000-$210,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": True,
        },
        {
            "title": "Remote Software Engineer - Python/Django",
            "company": "RemoteFirst Tech",
            "location": "Remote (USA)",
            "description": "Fully remote Python/Django engineer. Build and maintain REST APIs, work with PostgreSQL, Redis, Celery, Docker. Experience with AWS, CI/CD, and testing required. Async-first team with flexible hours.",
            "url": "https://example.com/jobs/remote-python",
            "source": "mock", "job_type": "Full-time", "salary": "$130,000-$170,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": True,
        },
        {
            "title": "Site Reliability Engineer",
            "company": "BigScale Inc.",
            "location": "San Jose, CA",
            "description": "SRE role: manage production infrastructure using Kubernetes, Docker, Terraform, AWS. Strong Linux, Python, and shell scripting skills. Implement monitoring with Prometheus/Grafana. On-call rotation.",
            "url": "https://example.com/jobs/sre",
            "source": "mock", "job_type": "Full-time", "salary": "$145,000-$190,000",
            "date_posted": datetime.now().strftime("%Y-%m-%d"), "remote": False,
        },
    ]


# ============================================================
# Helpers
# ============================================================

def _strip_html(text):
    """Remove HTML tags from text."""
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()


def _format_salary(min_sal, max_sal):
    if min_sal and max_sal:
        return f"${int(min_sal):,}-${int(max_sal):,}"
    if min_sal:
        return f"${int(min_sal):,}+"
    if max_sal:
        return f"Up to ${int(max_sal):,}"
    return ""


# ============================================================
# Main aggregator
# ============================================================

SOURCE_FETCHERS = {
    "jsearch": fetch_jsearch,
    "adzuna": fetch_adzuna,
    "remotive": fetch_remotive,
    "themuse": fetch_themuse,
    "usajobs": fetch_usajobs,
    "mock": fetch_mock,
}


def get_available_sources():
    """Return list of sources that have valid API keys configured."""
    available = ["mock", "remotive", "themuse"]  # Always available (free/no key)
    if Config.RAPIDAPI_KEY:
        available.append("jsearch")
    if Config.ADZUNA_APP_ID and Config.ADZUNA_APP_KEY:
        available.append("adzuna")
    if Config.USAJOBS_API_KEY:
        available.append("usajobs")
    return available


def aggregate_jobs(query, location="", sources=None):
    """
    Fetch jobs from multiple sources in parallel, deduplicate, and save to DB.
    Returns list of normalized job dicts with DB ids.
    """
    if sources is None:
        sources = get_available_sources()

    all_jobs = []
    source_results = {}

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {}
        for source in sources:
            fetcher = SOURCE_FETCHERS.get(source)
            if not fetcher:
                continue
            if source in ("jsearch", "adzuna", "usajobs"):
                futures[executor.submit(fetcher, query, location)] = source
            elif source == "remotive":
                futures[executor.submit(fetcher, query)] = source
            elif source == "themuse":
                futures[executor.submit(fetcher, query, location)] = source
            elif source == "mock":
                futures[executor.submit(fetcher, query)] = source

        for future in as_completed(futures):
            source = futures[future]
            try:
                jobs = future.result()
                source_results[source] = len(jobs)
                all_jobs.extend(jobs)
                logger.info(f"[{source}] fetched {len(jobs)} jobs")
            except Exception as e:
                source_results[source] = 0
                logger.error(f"[{source}] error: {e}")

    # Save to DB (dedup handled by UNIQUE constraint)
    if all_jobs:
        job_ids = models.save_jobs(all_jobs)
        for i, job in enumerate(all_jobs):
            job["id"] = job_ids[i]

    # Log search
    models.save_search_history(query, location, list(source_results.keys()), len(all_jobs))

    return all_jobs, source_results


def run_scheduled_fetch(resume_skills=None):
    """
    Run a scheduled fetch using the primary resume's skills.
    Called by the scheduler or manually.
    """
    if not resume_skills:
        primary = models.get_primary_resume()
        if not primary:
            logger.warning("No resume found for scheduled fetch")
            return 0
        resume_skills = primary["skills"]

    # Build multiple search queries from skills to get broad coverage
    queries = _build_search_queries(resume_skills)
    sources = get_available_sources()

    total_new = 0
    all_source_results = {}

    for query in queries:
        jobs, source_results = aggregate_jobs(query, sources=sources)
        total_new += len(jobs)
        for src, cnt in source_results.items():
            all_source_results[src] = all_source_results.get(src, 0) + cnt

    total_in_db = models.get_job_stats()["total"]
    models.log_scheduler_run(
        sources_queried=list(all_source_results.keys()),
        new_jobs=total_new,
        total_jobs=total_in_db,
    )

    logger.info(f"Scheduled fetch complete: {total_new} new jobs from {len(all_source_results)} sources")
    return total_new


def _build_search_queries(skills, max_queries=5):
    """Build diverse search queries from skills to maximize job coverage."""
    if not skills:
        return ["software engineer"]

    queries = []
    # Primary query: top skills combined
    queries.append(" ".join(skills[:3]))

    # Role-based queries based on detected skill clusters
    skill_set = set(s.lower() for s in skills)
    role_keywords = {
        "python developer": {"python", "django", "flask", "fastapi"},
        "javascript developer": {"javascript", "react", "node.js", "typescript"},
        "data scientist": {"machine learning", "data science", "pandas", "tensorflow"},
        "devops engineer": {"docker", "kubernetes", "terraform", "ci/cd"},
        "cloud engineer": {"aws", "azure", "gcp", "cloud architecture"},
        "backend engineer": {"java", "spring", "postgresql", "microservices"},
        "frontend developer": {"react", "angular", "vue", "css"},
        "full stack developer": {"javascript", "python", "react", "sql"},
    }

    for role, required_skills in role_keywords.items():
        if skill_set & required_skills:
            queries.append(role)

    return queries[:max_queries]
