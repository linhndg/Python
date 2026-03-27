import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "docx"}
    DATABASE_PATH = os.path.join(BASE_DIR, "resume_job_matcher.db")
    RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST = "jsearch.p.rapidapi.com"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
