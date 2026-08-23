"""
LLM-powered semantic match scoring.

This is the "brain" of the screener: given a resume's extracted profile
and a job description, ask Claude to act as a technical recruiter and
produce a structured 1-10 fit score with justification and a skills gap
analysis. We ask for strict JSON output so the API layer never has to
regex-parse free text.
"""
import json
import os
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env "
                "(see .env.example) before requesting a match score."
            )
        _client = Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are an experienced technical recruiter and resume \
screener. You evaluate how well a candidate's resume fits a specific job \
description. You are rigorous, evidence-based, and avoid vague praise. You \
only give credit for skills/experience that are actually evidenced in the \
resume text, not implied or assumed. You always respond with ONLY a single \
valid JSON object and nothing else - no markdown fences, no preamble."""

USER_PROMPT_TEMPLATE = """Compare the following resume with this job \
description and rate the candidate's fit on a scale of 1-10, with a clear \
justification.

JOB DESCRIPTION
Title: {job_title}
---
{job_description}
---

CANDIDATE RESUME
Filename: {filename}
Extracted skills (rule-based, may be incomplete): {extracted_skills}
Extracted education: {extracted_education}
Estimated years of experience: {years_experience}
---
Full resume text:
{resume_text}
---

Evaluate the fit and respond with ONLY this JSON structure (no other text):
{{
  "match_score": <integer 1-10>,
  "justification": "<2-4 sentence explanation citing specific evidence from \
the resume, referencing both strengths and gaps>",
  "matched_skills": ["<skills/requirements from the JD that the resume \
clearly demonstrates>"],
  "missing_skills": ["<important skills/requirements from the JD that the \
resume does NOT demonstrate>"],
  "recommendation": "<one of: 'Strong Match', 'Possible Match', 'Weak Match'>"
}}

Scoring guide:
- 9-10: Directly meets nearly all core requirements with strong evidence
- 7-8: Meets most core requirements, minor gaps
- 5-6: Meets some requirements, notable gaps
- 3-4: Meets few requirements
- 1-2: Largely irrelevant to the role
"""


def score_resume_against_job(
    job_title: str,
    job_description: str,
    filename: str,
    resume_text: str,
    extracted_skills: list,
    extracted_education: list,
    years_experience: float,
) -> dict:
    """Calls Claude to compute a semantic match score. Returns a dict with
    match_score, justification, matched_skills, missing_skills, recommendation.
    """
    client = get_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        job_title=job_title,
        job_description=job_description,
        filename=filename,
        extracted_skills=", ".join(extracted_skills) or "none detected",
        extracted_education=", ".join(extracted_education) or "none detected",
        years_experience=years_experience,
        # Cap resume text length to keep prompts efficient
        resume_text=resume_text[:12000],
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # Defensive cleanup in case the model wraps output in a code fence anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse LLM response as JSON: {e}\nRaw: {raw_text}")

    return {
        "match_score": float(parsed.get("match_score", 0)),
        "justification": parsed.get("justification", ""),
        "matched_skills": parsed.get("matched_skills", []),
        "missing_skills": parsed.get("missing_skills", []),
        "recommendation": parsed.get("recommendation", ""),
    }
