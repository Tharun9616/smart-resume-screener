"""
Resume parsing utilities.

Two responsibilities, kept deliberately separate from the LLM matcher:
1. extract_text_from_file  -> pull raw text out of an uploaded PDF/TXT
2. extract_structured_data -> pull skills / education / experience out
   of that raw text using lightweight rules + regex.

Keeping extraction rule-based (rather than an LLM call per resume) makes
it fast, free, and deterministic. The LLM budget is reserved for the part
that actually needs judgment: semantic match scoring (see llm_matcher.py).
"""
import io
import re
from typing import List, Tuple

import pdfplumber

# A reasonably broad skills taxonomy. Extend as needed.
SKILL_KEYWORDS = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql",
    # Web / backend
    "react", "angular", "vue", "next.js", "node.js", "express", "django",
    "flask", "fastapi", "spring", "spring boot", "rails", ".net", "graphql",
    "rest api", "html", "css", "tailwind",
    # Data / ML
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "keras",
    "llm", "large language models", "prompt engineering", "generative ai",
    "data science", "data analysis", "data engineering", "etl",
    # Cloud / infra
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "ci/cd", "jenkins", "github actions", "linux",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "sqlite",
    "dynamodb", "cassandra",
    # Practices
    "agile", "scrum", "microservices", "system design", "unit testing",
    "tdd", "git", "devops",
]

DEGREE_PATTERNS = [
    r"\b(b\.?tech|bachelor of technology)\b",
    r"\b(m\.?tech|master of technology)\b",
    r"\b(b\.?sc|bachelor of science)\b",
    r"\b(m\.?sc|master of science)\b",
    r"\b(b\.?e\.?|bachelor of engineering)\b",
    r"\b(m\.?e\.?|master of engineering)\b",
    r"\b(mba)\b",
    r"\b(phd|ph\.d\.?|doctorate)\b",
    r"\b(bachelor'?s? degree)\b",
    r"\b(master'?s? degree)\b",
    r"\b(b\.?a\.?|bachelor of arts)\b",
    r"\b(m\.?a\.?|master of arts)\b",
]

YEARS_EXP_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s*(?:of)?\s*experience", re.IGNORECASE
)

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def extract_text_from_file(filename: str, content: bytes) -> str:
    """Extract raw text from an uploaded resume (.pdf or .txt)."""
    if filename.lower().endswith(".pdf"):
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts).strip()
    else:
        # Treat as plain text
        return content.decode("utf-8", errors="ignore").strip()


def guess_candidate_name(text: str, filename: str) -> str:
    """Best-effort candidate name guess: first non-empty line, else filename."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like headers/contact info
        if EMAIL_PATTERN.search(line) or any(ch.isdigit() for ch in line):
            continue
        if 2 <= len(line.split()) <= 5 and len(line) < 60:
            return line
        break
    return filename.rsplit(".", 1)[0]


def extract_skills(text: str) -> List[str]:
    lower = text.lower()
    found = set()
    for skill in SKILL_KEYWORDS:
        # word-boundary-ish match, tolerant of punctuation like "c++"
        pattern = re.escape(skill)
        if re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", lower):
            found.add(skill)
    return sorted(found)


def extract_education(text: str) -> List[str]:
    lower = text.lower()
    found = set()
    for pattern in DEGREE_PATTERNS:
        for match in re.finditer(pattern, lower):
            found.add(match.group(0).strip().upper())
    return sorted(found)


def extract_years_experience(text: str) -> Tuple[float, List[str]]:
    """
    Returns (total_years_estimate, list_of_experience_snippets).
    Looks for explicit "X years of experience" phrases; falls back to
    counting distinct date ranges (YYYY - YYYY) as a rough proxy.
    """
    matches = YEARS_EXP_PATTERN.findall(text)
    years_estimate = max((float(m) for m in matches), default=0.0)

    # Grab lines that look like role/date entries, e.g. "Software Engineer, Acme (2019-2022)"
    date_range_pattern = re.compile(
        r"([A-Za-z ,.&]{3,60})\(?\b((?:19|20)\d{2})\s*[-–—to]+\s*((?:19|20)\d{2}|present|current)\b\)?",
        re.IGNORECASE,
    )
    snippets = []
    for m in date_range_pattern.finditer(text):
        role_context, start, end = m.groups()
        snippets.append(f"{role_context.strip(' ,.-')} ({start}–{end})")

    if not years_estimate and snippets:
        # Rough fallback: sum up date ranges we found (deduplicated by start year)
        seen_starts = set()
        total = 0.0
        for m in date_range_pattern.finditer(text):
            _, start, end = m.groups()
            if start in seen_starts:
                continue
            seen_starts.add(start)
            end_year = 2026 if end.lower() in ("present", "current") else int(end)
            total += max(0, end_year - int(start))
        years_estimate = total

    return years_estimate, snippets[:10]


def extract_structured_data(text: str) -> dict:
    years, exp_snippets = extract_years_experience(text)
    return {
        "skills": extract_skills(text),
        "education": extract_education(text),
        "experience": exp_snippets,
        "total_years_experience": years,
    }
