import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, JSON
from sqlalchemy.orm import relationship
from database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    resumes = relationship("Resume", back_populates="job", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    candidate_name = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=False)

    # Structured, extracted data (stored as JSON)
    skills = Column(JSON, default=list)
    education = Column(JSON, default=list)
    experience = Column(JSON, default=list)
    total_years_experience = Column(Float, nullable=True)

    # LLM scoring results
    match_score = Column(Float, nullable=True)          # 1-10
    justification = Column(Text, nullable=True)
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    job = relationship("Job", back_populates="resumes")
