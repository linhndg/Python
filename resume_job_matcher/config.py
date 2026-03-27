import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "docx"}
    DATABASE_PATH = os.path.join(BASE_DIR, "resume_job_matcher.db")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # Job API Keys (set via environment variables)
    RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST = "jsearch.p.rapidapi.com"
    ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
    USAJOBS_API_KEY = os.environ.get("USAJOBS_API_KEY", "")
    USAJOBS_EMAIL = os.environ.get("USAJOBS_EMAIL", "")

    # Scheduler settings
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_INTERVAL_HOURS = int(os.environ.get("SCHEDULER_INTERVAL_HOURS", "24"))

    # User profile for auto-fill extension
    PROFILE_EXPORT_PATH = os.path.join(BASE_DIR, "profile_export.json")
