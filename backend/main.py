"""
Smart Resume Screener - FastAPI backend.

Endpoints:
  POST   /jobs                          create a job description
  GET    /jobs                          list jobs
  GET    /jobs/{job_id}                 get one job
  POST   /jobs/{job_id}/resumes         upload one or more resumes (PDF/TXT)
                                         -> parses + extracts structured data
  POST   /resumes/{resume_id}/score     run LLM match scoring for a resume
  POST   /jobs/{job_id}/score_all       score every un-scored resume for a job
  GET    /jobs/{job_id}/candidates      list resumes for a job, sorted by
                                         match_score desc (the "shortlist")
  DELETE /jobs/{job_id}                 delete a job and its resumes
"""
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
import schemas
from database import engine, get_db
from parser import extract_text_from_file, extract_structured_data, guess_candidate_name
from llm_matcher import score_resume_against_job

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Resume Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- Jobs ----

@app.post("/jobs", response_model=schemas.JobOut)
def create_job(job: schemas.JobCreate, db: Session = Depends(get_db)):
    db_job = models.Job(title=job.title, description=job.description)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@app.get("/jobs", response_model=List[schemas.JobOut])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(models.Job).order_by(desc(models.Job.created_at)).all()


@app.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- Resumes ----

@app.post("/jobs/{job_id}/resumes", response_model=List[schemas.ResumeOut])
async def upload_resumes(
    job_id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):
    job = db.query(models.Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    created = []
    for f in files:
        content = await f.read()
        if not f.filename.lower().endswith((".pdf", ".txt")):
            raise HTTPException(400, f"Unsupported file type: {f.filename}")

        text = extract_text_from_file(f.filename, content)
        if not text.strip():
            raise HTTPException(400, f"Could not extract any text from {f.filename}")

        structured = extract_structured_data(text)
        candidate_name = guess_candidate_name(text, f.filename)

        resume = models.Resume(
            job_id=job_id,
            filename=f.filename,
            candidate_name=candidate_name,
            raw_text=text,
            skills=structured["skills"],
            education=structured["education"],
            experience=structured["experience"],
            total_years_experience=structured["total_years_experience"],
        )
        db.add(resume)
        created.append(resume)

    db.commit()
    for r in created:
        db.refresh(r)
    return created


@app.post("/resumes/{resume_id}/score", response_model=schemas.ResumeOut)
def score_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(models.Resume).get(resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    job = resume.job

    try:
        result = score_resume_against_job(
            job_title=job.title,
            job_description=job.description,
            filename=resume.filename,
            resume_text=resume.raw_text,
            extracted_skills=resume.skills or [],
            extracted_education=resume.education or [],
            years_experience=resume.total_years_experience or 0,
        )
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    resume.match_score = result["match_score"]
    resume.justification = result["justification"]
    resume.matched_skills = result["matched_skills"]
    resume.missing_skills = result["missing_skills"]
    db.commit()
    db.refresh(resume)
    return resume


@app.post("/jobs/{job_id}/score_all", response_model=List[schemas.ResumeOut])
def score_all(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    unscored = (
        db.query(models.Resume)
        .filter(models.Resume.job_id == job_id, models.Resume.match_score.is_(None))
        .all()
    )
    for resume in unscored:
        try:
            result = score_resume_against_job(
                job_title=job.title,
                job_description=job.description,
                filename=resume.filename,
                resume_text=resume.raw_text,
                extracted_skills=resume.skills or [],
                extracted_education=resume.education or [],
                years_experience=resume.total_years_experience or 0,
            )
            resume.match_score = result["match_score"]
            resume.justification = result["justification"]
            resume.matched_skills = result["matched_skills"]
            resume.missing_skills = result["missing_skills"]
        except RuntimeError as e:
            raise HTTPException(502, str(e))
    db.commit()

    return (
        db.query(models.Resume)
        .filter(models.Resume.job_id == job_id)
        .order_by(desc(models.Resume.match_score))
        .all()
    )


@app.get("/jobs/{job_id}/candidates", response_model=List[schemas.ResumeOut])
def get_candidates(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return (
        db.query(models.Resume)
        .filter(models.Resume.job_id == job_id)
        .order_by(desc(models.Resume.match_score))
        .all()
    )


@app.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(models.Resume).get(resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    db.delete(resume)
    db.commit()
    return {"ok": True}


# Serve the static dashboard at "/"
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
