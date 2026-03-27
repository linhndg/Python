import json
import sqlite3

from config import Config


def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            full_text TEXT,
            skills TEXT,
            experience TEXT,
            education TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            description TEXT,
            url TEXT,
            source TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(title, company, url)
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id INTEGER REFERENCES resumes(id),
            job_id INTEGER REFERENCES jobs(id),
            cover_letter TEXT,
            match_score REAL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'submitted'
        );
    """)
    conn.commit()
    conn.close()


def save_resume(filename, full_text, skills, experience, education):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO resumes (filename, full_text, skills, experience, education) VALUES (?, ?, ?, ?, ?)",
        (filename, full_text, json.dumps(skills), json.dumps(experience), json.dumps(education)),
    )
    resume_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return resume_id


def get_resume(resume_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "filename": row["filename"],
        "full_text": row["full_text"],
        "skills": json.loads(row["skills"]) if row["skills"] else [],
        "experience": json.loads(row["experience"]) if row["experience"] else [],
        "education": json.loads(row["education"]) if row["education"] else [],
        "uploaded_at": row["uploaded_at"],
    }


def save_job(title, company, location, description, url, source):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO jobs (title, company, location, description, url, source) VALUES (?, ?, ?, ?, ?, ?)",
            (title, company, location, description, url, source),
        )
        job_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return job_id


def get_job(job_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def save_jobs(jobs_list):
    conn = get_db()
    ids = []
    for job in jobs_list:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO jobs (title, company, location, description, url, source) VALUES (?, ?, ?, ?, ?, ?)",
            (job["title"], job["company"], job["location"], job["description"], job["url"], job["source"]),
        )
        if cursor.lastrowid:
            ids.append(cursor.lastrowid)
        else:
            row = conn.execute(
                "SELECT id FROM jobs WHERE title = ? AND company = ? AND url = ?",
                (job["title"], job["company"], job["url"]),
            ).fetchone()
            ids.append(row["id"] if row else None)
    conn.commit()
    conn.close()
    return ids


def save_application(resume_id, job_id, cover_letter, match_score):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO applications (resume_id, job_id, cover_letter, match_score) VALUES (?, ?, ?, ?)",
        (resume_id, job_id, cover_letter, match_score),
    )
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return app_id


def get_applications(resume_id=None):
    conn = get_db()
    if resume_id:
        rows = conn.execute(
            """SELECT a.*, j.title as job_title, j.company, j.url as job_url, r.filename
               FROM applications a
               JOIN jobs j ON a.job_id = j.id
               JOIN resumes r ON a.resume_id = r.id
               WHERE a.resume_id = ?
               ORDER BY a.applied_at DESC""",
            (resume_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT a.*, j.title as job_title, j.company, j.url as job_url, r.filename
               FROM applications a
               JOIN jobs j ON a.job_id = j.id
               JOIN resumes r ON a.resume_id = r.id
               ORDER BY a.applied_at DESC"""
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
