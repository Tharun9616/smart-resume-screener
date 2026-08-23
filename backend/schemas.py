from typing import List, Optional
from pydantic import BaseModel


class JobCreate(BaseModel):
    title: str
    description: str


class JobOut(BaseModel):
    id: int
    title: str
    description: str

    class Config:
        from_attributes = True


class ResumeOut(BaseModel):
    id: int
    job_id: int
    filename: str
    candidate_name: Optional[str]
    skills: List[str] = []
    education: List[str] = []
    experience: List[str] = []
    total_years_experience: Optional[float]
    match_score: Optional[float]
    justification: Optional[str]
    matched_skills: List[str] = []
    missing_skills: List[str] = []

    class Config:
        from_attributes = True
