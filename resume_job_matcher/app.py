import json
import os

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from config import Config
import models
import resume_parser
import job_aggregator
import job_matcher
import application_generator

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
models.init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


# ============================================================
# Dashboard
# ============================================================

@app.route("/")
def dashboard():
    stats = models.get_job_stats()
    resumes = models.get_all_resumes()
    recent_jobs = models.get_all_jobs({"limit": 10})

    # Score recent jobs if we have a resume
    primary = models.get_primary_resume()
    if primary and recent_jobs:
        resume_data = {
            "skills": primary["skills"],
            "experience": primary["experience"],
            "education": primary["education"],
        }
        for job in recent_jobs:
            job["match_score"] = job_matcher.score_job(resume_data, job)
        recent_jobs.sort(key=lambda j: j["match_score"], reverse=True)

    logs = models.get_scheduler_logs(5)
    sources = job_aggregator.get_available_sources()
    return render_template("dashboard.html", stats=stats, resumes=resumes,
                           recent_jobs=recent_jobs, logs=logs, sources=sources,
                           primary=primary)


# ============================================================
# Resume Management
# ============================================================

@app.route("/resumes")
def resumes_list():
    resumes = models.get_all_resumes()
    return render_template("resumes.html", resumes=resumes)


@app.route("/upload", methods=["POST"])
def upload():
    if "resume" not in request.files:
        flash("No file selected.", "error")
        return redirect(request.referrer or url_for("dashboard"))

    file = request.files["resume"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(request.referrer or url_for("dashboard"))

    if not allowed_file(file.filename):
        flash("Only PDF and DOCX files are supported.", "error")
        return redirect(request.referrer or url_for("dashboard"))

    filename = secure_filename(file.filename)
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        parsed = resume_parser.parse_resume(filepath)
    except Exception as e:
        flash(f"Error parsing resume: {e}", "error")
        return redirect(request.referrer or url_for("dashboard"))

    contact_info = request.form.get("contact_info")
    if contact_info:
        try:
            contact_info = json.loads(contact_info)
        except json.JSONDecodeError:
            contact_info = {}
    else:
        contact_info = {}

    resume_id = models.save_resume(
        filename=filename,
        full_text=parsed["full_text"],
        skills=parsed["skills"],
        experience=parsed["experience"],
        education=parsed["education"],
        contact_info=contact_info,
    )
    models.set_primary_resume(resume_id)

    flash("Resume uploaded and parsed successfully!", "success")
    return redirect(url_for("view_resume", resume_id=resume_id))


@app.route("/resume/<int:resume_id>")
def view_resume(resume_id):
    resume = models.get_resume(resume_id)
    if not resume:
        flash("Resume not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("resume_view.html", resume=resume)


@app.route("/resume/<int:resume_id>/set-primary", methods=["POST"])
def set_primary(resume_id):
    models.set_primary_resume(resume_id)
    flash("Primary resume updated.", "success")
    return redirect(request.referrer or url_for("resumes_list"))


@app.route("/resume/<int:resume_id>/contact", methods=["POST"])
def update_contact(resume_id):
    contact = {
        "full_name": request.form.get("full_name", ""),
        "email": request.form.get("email", ""),
        "phone": request.form.get("phone", ""),
        "address": request.form.get("address", ""),
        "city": request.form.get("city", ""),
        "state": request.form.get("state", ""),
        "zip_code": request.form.get("zip_code", ""),
        "linkedin": request.form.get("linkedin", ""),
        "website": request.form.get("website", ""),
    }
    models.update_resume_contact(resume_id, contact)
    flash("Contact information updated.", "success")
    return redirect(url_for("view_resume", resume_id=resume_id))


# ============================================================
# Job Board
# ============================================================

@app.route("/jobs")
def job_board():
    filters = {
        "source": request.args.get("source", ""),
        "remote": request.args.get("remote", ""),
        "location": request.args.get("location", ""),
        "company": request.args.get("company", ""),
        "status": request.args.get("status", ""),
        "is_saved": request.args.get("saved", ""),
        "search": request.args.get("q", ""),
        "limit": 100,
    }
    # Clean empty filters
    filters = {k: v for k, v in filters.items() if v}
    if "limit" not in filters:
        filters["limit"] = 100

    jobs = models.get_all_jobs(filters)

    # Score jobs against primary resume
    primary = models.get_primary_resume()
    min_score = request.args.get("min_score", type=float)
    if primary:
        resume_data = {
            "skills": primary["skills"],
            "experience": primary["experience"],
            "education": primary["education"],
        }
        for job in jobs:
            job["match_score"] = job_matcher.score_job(resume_data, job)
        jobs.sort(key=lambda j: j["match_score"], reverse=True)
        if min_score is not None:
            jobs = [j for j in jobs if j["match_score"] >= min_score / 100.0]

    sources = job_aggregator.get_available_sources()
    return render_template("job_board.html", jobs=jobs, filters=request.args,
                           sources=sources, primary=primary)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = models.get_job(job_id)
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("job_board"))

    primary = models.get_primary_resume()
    match_score = 0
    if primary:
        resume_data = {
            "skills": primary["skills"],
            "experience": primary["experience"],
            "education": primary["education"],
        }
        match_score = job_matcher.score_job(resume_data, job)

    return render_template("job_detail.html", job=job, match_score=match_score, resume=primary)


@app.route("/jobs/<int:job_id>/save", methods=["POST"])
def save_job(job_id):
    models.toggle_save_job(job_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(request.referrer or url_for("job_board"))


@app.route("/jobs/<int:job_id>/status", methods=["POST"])
def update_job_status(job_id):
    status = request.form.get("status", "new")
    models.update_job_status(job_id, status)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    flash(f"Job status updated to '{status}'.", "success")
    return redirect(request.referrer or url_for("job_board"))


# ============================================================
# Search / Fetch Jobs
# ============================================================

@app.route("/search", methods=["GET", "POST"])
def search_jobs():
    if request.method == "POST":
        query = request.form.get("query", "")
        location = request.form.get("location", "")
        sources = request.form.getlist("sources")

        if not query:
            # Use primary resume skills
            primary = models.get_primary_resume()
            if primary and primary["skills"]:
                query = " ".join(primary["skills"][:5])
            else:
                flash("Enter a search query or upload a resume first.", "error")
                return redirect(url_for("search_jobs"))

        if not sources:
            sources = None  # Use all available

        jobs, source_results = job_aggregator.aggregate_jobs(query, location, sources)

        # Score the results
        primary = models.get_primary_resume()
        if primary:
            resume_data = {
                "skills": primary["skills"],
                "experience": primary["experience"],
                "education": primary["education"],
            }
            jobs = job_matcher.rank_jobs(resume_data, jobs)

        flash(f"Found {len(jobs)} jobs from {len(source_results)} sources.", "success")
        return render_template("search_results.html", jobs=jobs, query=query,
                               location=location, source_results=source_results,
                               primary=primary)

    sources = job_aggregator.get_available_sources()
    primary = models.get_primary_resume()
    return render_template("search.html", sources=sources, primary=primary)


@app.route("/fetch-now", methods=["POST"])
def fetch_now():
    """Trigger an immediate job fetch."""
    from job_aggregator import run_scheduled_fetch
    count = run_scheduled_fetch()
    flash(f"Fetched {count} jobs from all configured sources.", "success")
    return redirect(url_for("dashboard"))


# ============================================================
# Applications
# ============================================================

@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_job(job_id):
    primary = models.get_primary_resume()
    if not primary:
        flash("Upload a resume first.", "error")
        return redirect(url_for("dashboard"))

    job = models.get_job(job_id)
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("job_board"))

    resume_data = {
        "skills": primary["skills"],
        "experience": primary["experience"],
        "education": primary["education"],
    }

    cover_letter = application_generator.generate_cover_letter(resume_data, job)
    match_score = job_matcher.score_job(resume_data, job)

    models.save_application(primary["id"], job_id, cover_letter, match_score)
    flash(f"Application submitted to {job['company']} for {job['title']}!", "success")

    return render_template(
        "cover_letter.html",
        resume=primary, job=job, cover_letter=cover_letter, match_score=match_score,
    )


@app.route("/applications")
def applications():
    resume_id = request.args.get("resume_id", type=int)
    apps = models.get_applications(resume_id)
    return render_template("applications.html", applications=apps)


@app.route("/applications/<int:app_id>/status", methods=["POST"])
def update_app_status(app_id):
    status = request.form.get("status", "submitted")
    models.update_application_status(app_id, status)
    flash(f"Application status updated to '{status}'.", "success")
    return redirect(url_for("applications"))


# ============================================================
# Profile Export API (for Chrome Extension)
# ============================================================

@app.route("/api/profile")
def api_profile():
    """Export user profile data as JSON for the Chrome extension."""
    primary = models.get_primary_resume()
    if not primary:
        return jsonify({"error": "No resume uploaded"}), 404

    profile = {
        "contact": primary.get("contact_info", {}),
        "skills": primary["skills"],
        "experience": primary["experience"],
        "education": primary["education"],
        "summary": _generate_summary(primary),
    }
    return jsonify(profile)


@app.route("/api/profile/export", methods=["POST"])
def export_profile():
    """Save profile to JSON file for Chrome extension import."""
    primary = models.get_primary_resume()
    if not primary:
        return jsonify({"error": "No resume uploaded"}), 404

    profile = {
        "contact": primary.get("contact_info", {}),
        "skills": primary["skills"],
        "experience": primary["experience"],
        "education": primary["education"],
        "summary": _generate_summary(primary),
    }

    with open(Config.PROFILE_EXPORT_PATH, "w") as f:
        json.dump(profile, f, indent=2)

    flash("Profile exported for Chrome extension.", "success")
    return redirect(url_for("view_resume", resume_id=primary["id"]))


@app.route("/api/jobs")
def api_jobs():
    """API endpoint for job data (used by extension and AJAX)."""
    filters = {k: request.args.get(k) for k in
               ["source", "remote", "location", "company", "status", "search"]
               if request.args.get(k)}
    filters["limit"] = request.args.get("limit", 50, type=int)
    jobs = models.get_all_jobs(filters)
    return jsonify(jobs)


def _generate_summary(resume):
    exp = resume.get("experience", [])
    skills = resume.get("skills", [])
    summary = ""
    if exp:
        summary += f"Professional with {len(exp)} roles. "
    if skills:
        summary += f"Key skills: {', '.join(skills[:10])}."
    return summary


# ============================================================
# Error Handlers
# ============================================================

@app.errorhandler(413)
def file_too_large(e):
    flash("File is too large. Maximum size is 5 MB.", "error")
    return redirect(url_for("dashboard"))


# ============================================================
# Start scheduler on app start
# ============================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    from scheduler import start_scheduler
    start_scheduler(app)
    app.run(debug=True, port=5000, use_reloader=False)
