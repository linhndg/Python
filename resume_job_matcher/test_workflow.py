"""Test the full workflow: parse resume -> search jobs -> match -> generate cover letter -> apply."""

import resume_parser
import job_searcher
import job_matcher
import application_generator
import models

models.init_db()

# Step 1: Parse the sample resume
print("=" * 60)
print("STEP 1: Parsing Resume")
print("=" * 60)
parsed = resume_parser.parse_resume("uploads/sample_resume.docx")

print(f"\nExtracted {len(parsed['skills'])} skills:")
print(", ".join(parsed["skills"]))

print(f"\nExtracted {len(parsed['experience'])} experience entries:")
for exp in parsed["experience"]:
    print(f"  - {exp['title']} at {exp['company']} ({exp['duration']})")

print(f"\nExtracted {len(parsed['education'])} education entries:")
for edu in parsed["education"]:
    print(f"  - {edu['degree']} {edu['field']} - {edu['institution']}")

# Save resume to DB
resume_id = models.save_resume(
    "sample_resume.docx", parsed["full_text"],
    parsed["skills"], parsed["experience"], parsed["education"]
)
print(f"\nResume saved with ID: {resume_id}")

# Step 2: Search for jobs
print("\n" + "=" * 60)
print("STEP 2: Searching for Matching Jobs")
print("=" * 60)
jobs = job_searcher.search_jobs(parsed["skills"])
print(f"Found {len(jobs)} jobs")

# Step 3: Rank jobs
print("\n" + "=" * 60)
print("STEP 3: Ranking Jobs by Match Score")
print("=" * 60)
resume_data = {
    "skills": parsed["skills"],
    "experience": parsed["experience"],
    "education": parsed["education"],
}
ranked = job_matcher.rank_jobs(resume_data, jobs)

for i, job in enumerate(ranked, 1):
    score_pct = job["match_score"] * 100
    print(f"  {i}. [{score_pct:5.1f}%] {job['title']} at {job['company']} ({job['location']})")

# Step 4: Generate cover letter for top match
print("\n" + "=" * 60)
print("STEP 4: Generating Cover Letter for Top Match")
print("=" * 60)
top_job = ranked[0]
cover_letter = application_generator.generate_cover_letter(resume_data, top_job)
print(f"\nJob: {top_job['title']} at {top_job['company']}")
print(f"Match Score: {top_job['match_score'] * 100:.1f}%")
print("\n--- Cover Letter ---")
print(cover_letter)

# Step 5: Save application
print("\n" + "=" * 60)
print("STEP 5: Submitting Application")
print("=" * 60)
app_id = models.save_application(resume_id, top_job["id"], cover_letter, top_job["match_score"])
print(f"Application #{app_id} submitted for {top_job['title']} at {top_job['company']}")

# Show all applications
apps = models.get_applications()
print(f"\nTotal applications: {len(apps)}")
for app in apps:
    print(f"  - {app['job_title']} at {app['company']} | Score: {app['match_score']*100:.1f}% | Status: {app['status']}")

print("\n" + "=" * 60)
print("WORKFLOW COMPLETE!")
print("=" * 60)
print("\nTo run the web app: cd resume_job_matcher && python app.py")
print("Then open http://localhost:5000 in your browser.")
