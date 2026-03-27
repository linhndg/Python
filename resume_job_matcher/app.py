import os

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from config import Config
import models
import resume_parser
import job_searcher
import job_matcher
import application_generator

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
models.init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "resume" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("index"))

    file = request.files["resume"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only PDF and DOCX files are supported.", "error")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        parsed = resume_parser.parse_resume(filepath)
    except Exception as e:
        flash(f"Error parsing resume: {e}", "error")
        return redirect(url_for("index"))

    resume_id = models.save_resume(
        filename=filename,
        full_text=parsed["full_text"],
        skills=parsed["skills"],
        experience=parsed["experience"],
        education=parsed["education"],
    )

    flash("Resume uploaded and parsed successfully!", "success")
    return redirect(url_for("view_resume", resume_id=resume_id))


@app.route("/resume/<int:resume_id>")
def view_resume(resume_id):
    resume = models.get_resume(resume_id)
    if not resume:
        flash("Resume not found.", "error")
        return redirect(url_for("index"))
    return render_template("resume_view.html", resume=resume)


@app.route("/search/<int:resume_id>", methods=["POST"])
def search_jobs(resume_id):
    resume = models.get_resume(resume_id)
    if not resume:
        flash("Resume not found.", "error")
        return redirect(url_for("index"))

    location = request.form.get("location", "")
    jobs = job_searcher.search_jobs(resume["skills"], location)
    ranked = job_matcher.rank_jobs(
        {"skills": resume["skills"], "experience": resume["experience"],
         "education": resume["education"]},
        jobs,
    )

    return render_template("job_results.html", resume=resume, jobs=ranked, location=location)


@app.route("/apply/<int:resume_id>/<int:job_id>", methods=["POST"])
def apply_job(resume_id, job_id):
    resume = models.get_resume(resume_id)
    job = models.get_job(job_id)
    if not resume or not job:
        flash("Resume or job not found.", "error")
        return redirect(url_for("index"))

    resume_data = {
        "skills": resume["skills"],
        "experience": resume["experience"],
        "education": resume["education"],
    }

    cover_letter = application_generator.generate_cover_letter(resume_data, job)
    match_score = job_matcher.score_job(resume_data, job)

    models.save_application(resume_id, job_id, cover_letter, match_score)
    flash(f"Application submitted to {job['company']} for {job['title']}!", "success")

    return render_template(
        "cover_letter.html",
        resume=resume, job=job, cover_letter=cover_letter, match_score=match_score,
    )


@app.route("/applications")
def applications():
    resume_id = request.args.get("resume_id", type=int)
    apps = models.get_applications(resume_id)
    return render_template("applications.html", applications=apps)


@app.errorhandler(413)
def file_too_large(e):
    flash("File is too large. Maximum size is 5 MB.", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
