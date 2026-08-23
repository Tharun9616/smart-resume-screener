# Smart Resume Screener

Parses resumes (PDF/TXT), extracts structured candidate data, and uses
Claude to semantically score each candidate against a job description —
producing a ranked, justified shortlist.

## Architecture

```
┌─────────────┐      ┌──────────────────────────────┐      ┌────────────┐
│  Dashboard  │ ───▶ │        FastAPI Backend         │ ───▶ │  SQLite DB │
│ (index.html)│ ◀─── │  main.py                       │ ◀─── │            │
└─────────────┘      │   ├─ parser.py   (rule-based    │      └────────────┘
                      │   │   text/skill/edu/exp        │
                      │   │   extraction from PDF/TXT)   │
                      │   └─ llm_matcher.py              │
                      │       (Claude semantic scoring)  │      ┌────────────┐
                      └──────────────────────────────┘ ───▶ │ Claude API │
                                                              └────────────┘
```

**Design decision — extraction vs. scoring split:**
Skill/education/experience extraction (`parser.py`) is rule-based (regex +
keyword taxonomy), not an LLM call. This keeps parsing fast, free, and
deterministic. The LLM (`llm_matcher.py`) is reserved for the step that
genuinely needs judgment — semantic fit scoring and justification — which
is where an LLM adds the most value per the project's LLM Usage Guidance.

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy (SQLite by default,
  swappable for Postgres/MySQL)
- **Resume parsing**: `pdfplumber` for PDF text extraction; regex/keyword
  based extraction of skills, education, and experience
- **LLM matching**: Anthropic Claude API (`claude-sonnet-4-6`), prompted to
  return strict JSON with a 1–10 score, justification, and matched/missing
  skills
- **Frontend**: single-page vanilla HTML/CSS/JS dashboard served by FastAPI
  (no build step required)
- **Storage**: SQLite file (`backend/resume_screener.db`), auto-created on
  first run

## Setup

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Add your Anthropic API key

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at https://console.anthropic.com/. Resume upload and structured
extraction work without a key; the "Score" step requires it.

### 3. Run the server

```bash
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — the dashboard is served automatically.

## Using it

1. **Create a job** — paste a title + job description (or use
   `sample_data/job_description.txt`).
2. **Upload resumes** — drag in PDF or TXT files (try the two samples in
   `sample_data/`).
3. **Score** — click "Score all with Claude" (or score one candidate at a
   time). Each candidate gets a 1–10 fit score, a written justification,
   and matched/missing skill tags, sorted highest-first.

## API reference

| Method | Path                         | Description                              |
|--------|------------------------------|-------------------------------------------|
| POST   | `/jobs`                      | Create a job description                  |
| GET    | `/jobs`                      | List jobs                                  |
| GET    | `/jobs/{id}`                 | Get one job                                |
| DELETE | `/jobs/{id}`                 | Delete a job + its resumes                 |
| POST   | `/jobs/{id}/resumes`         | Upload resume file(s) (multipart, PDF/TXT) |
| POST   | `/resumes/{id}/score`        | Score one resume with Claude               |
| POST   | `/jobs/{id}/score_all`       | Score all un-scored resumes for a job      |
| GET    | `/jobs/{id}/candidates`      | List candidates, sorted by score desc      |
| DELETE | `/resumes/{id}`              | Remove a resume                            |

Interactive API docs are available at `/docs` once the server is running.

## LLM prompt design

The core prompt (in `llm_matcher.py`) does three things deliberately:

1. **System prompt** frames Claude as a rigorous, evidence-based technical
   recruiter — explicitly told not to give credit for skills not evidenced
   in the resume text (reduces hallucinated fit).
2. **User prompt** includes both the raw resume text *and* the rule-based
   extraction (skills/education/years) as context, so Claude can cross-check
   its own read of the resume against the deterministic parse.
3. **Structured output**: the prompt demands a single JSON object with a
   fixed schema (`match_score`, `justification`, `matched_skills`,
   `missing_skills`, `recommendation`) and a numeric scoring rubric, so the
   API layer parses it directly with no fragile regex/text-scraping.

Example prompt shape (see `llm_matcher.py:USER_PROMPT_TEMPLATE` for the full
version):

> Compare the following resume with this job description and rate the
> candidate's fit on a scale of 1–10, with a clear justification... Respond
> with ONLY this JSON structure: `{"match_score": ..., "justification": ...,
> "matched_skills": [...], "missing_skills": [...], "recommendation": ...}`

## Project structure

```
smart-resume-screener/
├── backend/
│   ├── main.py            FastAPI app & routes
│   ├── models.py          SQLAlchemy ORM models
│   ├── schemas.py         Pydantic request/response schemas
│   ├── database.py        DB engine/session config
│   ├── parser.py          PDF/TXT text + structured data extraction
│   ├── llm_matcher.py     Claude prompt + scoring call
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html         Dashboard (vanilla JS, no build step)
├── sample_data/           Sample job description + 2 sample resumes
├── demo_script.md         Suggested script for the demo video
└── README.md
```

## Notes / possible extensions

- Swap SQLite for Postgres by changing `SQLALCHEMY_DATABASE_URL` in
  `database.py`.
- The skills taxonomy in `parser.py` is easily extended for other domains
  (e.g. sales, design) beyond the tech-focused list shipped here.
- Batch scoring (`score_all`) currently calls the LLM sequentially; for
  large resume volumes, parallelize with `asyncio.gather` and Anthropic's
  async client.
