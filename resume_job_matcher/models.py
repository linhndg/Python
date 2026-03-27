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
            contact_info TEXT DEFAULT '{}',
            is_primary INTEGER DEFAULT 0,
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
            job_type TEXT DEFAULT '',
            salary TEXT DEFAULT '',
            date_posted TEXT DEFAULT '',
            remote INTEGER DEFAULT 0,
            is_saved INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
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

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            location TEXT,
            sources TEXT,
            results_count INTEGER,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scheduler_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sources_queried TEXT,
            new_jobs_found INTEGER,
            total_jobs INTEGER,
            status TEXT DEFAULT 'success',
            error_message TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()


# --- Resume functions ---

def save_resume(filename, full_text, skills, experience, education, contact_info=None):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO resumes (filename, full_text, skills, experience, education, contact_info) VALUES (?, ?, ?, ?, ?, ?)",
        (filename, full_text, json.dumps(skills), json.dumps(experience),
         json.dumps(education), json.dumps(contact_info or {})),
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
    result = {
        "id": row["id"],
        "filename": row["filename"],
        "full_text": row["full_text"],
        "skills": json.loads(row["skills"]) if row["skills"] else [],
        "experience": json.loads(row["experience"]) if row["experience"] else [],
        "education": json.loads(row["education"]) if row["education"] else [],
        "uploaded_at": row["uploaded_at"],
        "is_primary": row["is_primary"],
    }
    try:
        result["contact_info"] = json.loads(row["contact_info"]) if row["contact_info"] else {}
    except (KeyError, json.JSONDecodeError):
        result["contact_info"] = {}
    return result


def get_all_resumes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM resumes ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    resumes = []
    for row in rows:
        resumes.append({
            "id": row["id"],
            "filename": row["filename"],
            "skills": json.loads(row["skills"]) if row["skills"] else [],
            "is_primary": row["is_primary"],
            "uploaded_at": row["uploaded_at"],
        })
    return resumes


def set_primary_resume(resume_id):
    conn = get_db()
    conn.execute("UPDATE resumes SET is_primary = 0")
    conn.execute("UPDATE resumes SET is_primary = 1 WHERE id = ?", (resume_id,))
    conn.commit()
    conn.close()


def get_primary_resume():
    conn = get_db()
    row = conn.execute("SELECT * FROM resumes WHERE is_primary = 1").fetchone()
    if not row:
        row = conn.execute("SELECT * FROM resumes ORDER BY uploaded_at DESC LIMIT 1").fetchone()
    conn.close()
    if row is None:
        return None
    result = {
        "id": row["id"],
        "filename": row["filename"],
        "full_text": row["full_text"],
        "skills": json.loads(row["skills"]) if row["skills"] else [],
        "experience": json.loads(row["experience"]) if row["experience"] else [],
        "education": json.loads(row["education"]) if row["education"] else [],
        "uploaded_at": row["uploaded_at"],
    }
    try:
        result["contact_info"] = json.loads(row["contact_info"]) if row["contact_info"] else {}
    except (KeyError, json.JSONDecodeError):
        result["contact_info"] = {}
    return result


def update_resume_contact(resume_id, contact_info):
    conn = get_db()
    conn.execute(
        "UPDATE resumes SET contact_info = ? WHERE id = ?",
        (json.dumps(contact_info), resume_id),
    )
    conn.commit()
    conn.close()


# --- Job functions ---

def save_jobs(jobs_list):
    conn = get_db()
    ids = []
    for job in jobs_list:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO jobs
               (title, company, location, description, url, source, job_type, salary, date_posted, remote)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job["title"], job["company"], job["location"], job["description"],
             job["url"], job["source"], job.get("job_type", ""),
             job.get("salary", ""), job.get("date_posted", ""),
             1 if job.get("remote") else 0),
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


def get_job(job_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_all_jobs(filters=None):
    conn = get_db()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if filters:
        if filters.get("source"):
            query += " AND source = ?"
            params.append(filters["source"])
        if filters.get("remote"):
            query += " AND remote = 1"
        if filters.get("location"):
            query += " AND location LIKE ?"
            params.append(f"%{filters['location']}%")
        if filters.get("company"):
            query += " AND company LIKE ?"
            params.append(f"%{filters['company']}%")
        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])
        if filters.get("is_saved"):
            query += " AND is_saved = 1"
        if filters.get("search"):
            query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s])

    query += " ORDER BY fetched_at DESC"

    if filters and filters.get("limit"):
        query += " LIMIT ?"
        params.append(filters["limit"])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_job_status(job_id, status):
    conn = get_db()
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()


def toggle_save_job(job_id):
    conn = get_db()
    row = conn.execute("SELECT is_saved FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row:
        new_val = 0 if row["is_saved"] else 1
        conn.execute("UPDATE jobs SET is_saved = ? WHERE id = ?", (new_val, job_id))
        conn.commit()
    conn.close()


def get_job_stats():
    conn = get_db()
    stats = {}
    stats["total"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    stats["new"] = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'").fetchone()[0]
    stats["saved"] = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_saved = 1").fetchone()[0]
    stats["applied"] = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    stats["sources"] = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source").fetchall():
        stats["sources"][row["source"]] = row["cnt"]
    conn.close()
    return stats


# --- Application functions ---

def save_application(resume_id, job_id, cover_letter, match_score):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO applications (resume_id, job_id, cover_letter, match_score) VALUES (?, ?, ?, ?)",
        (resume_id, job_id, cover_letter, match_score),
    )
    app_id = cursor.lastrowid
    conn.execute("UPDATE jobs SET status = 'applied' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return app_id


def get_applications(resume_id=None):
    conn = get_db()
    query = """SELECT a.*, j.title as job_title, j.company, j.url as job_url,
                      j.location as job_location, r.filename
               FROM applications a
               JOIN jobs j ON a.job_id = j.id
               JOIN resumes r ON a.resume_id = r.id"""
    params = []
    if resume_id:
        query += " WHERE a.resume_id = ?"
        params.append(resume_id)
    query += " ORDER BY a.applied_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_application_status(app_id, status):
    conn = get_db()
    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (status, app_id))
    conn.commit()
    conn.close()


# --- Scheduler log ---

def log_scheduler_run(sources_queried, new_jobs, total_jobs, status="success", error=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO scheduler_log (sources_queried, new_jobs_found, total_jobs, status, error_message) VALUES (?, ?, ?, ?, ?)",
        (json.dumps(sources_queried), new_jobs, total_jobs, status, error),
    )
    conn.commit()
    conn.close()


def get_scheduler_logs(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM scheduler_log ORDER BY run_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_search_history(query, location, sources, results_count):
    conn = get_db()
    conn.execute(
        "INSERT INTO search_history (query, location, sources, results_count) VALUES (?, ?, ?, ?)",
        (query, location, json.dumps(sources), results_count),
    )
    conn.commit()
    conn.close()
