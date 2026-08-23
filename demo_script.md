# Demo Video Script (2–3 minutes)

**0:00–0:20 — Intro**
"This is the Smart Resume Screener — it parses resumes, extracts structured
candidate data, and uses Claude to score each candidate against a job
description with a justified 1-10 fit score."

**0:20–0:45 — Create a job**
- Open the dashboard, click "+ New job"
- Paste in the sample job description (Backend Engineer, Python)
- Point out: title + full JD text is all that's needed

**0:45–1:15 — Upload resumes**
- Drag in `resume_priya_sharma.txt` and `resume_alex_chen.txt`
- Show the parsed output: skills, education, years of experience —
  explain this extraction is rule-based (fast, deterministic)

**1:15–2:00 — Score with Claude**
- Click "Score all with Claude"
- Walk through the results: score badges, color-coded (green/amber/red),
  written justification, matched vs. missing skill tags
- Point out how the strong-fit candidate (Priya) scores high with specific
  evidence cited, while the weak-fit candidate (Alex) scores low with a
  clear explanation of the gap

**2:00–2:30 — Code walkthrough**
- Briefly show `llm_matcher.py`: the system prompt (recruiter persona,
  evidence-based scoring) and the structured JSON output contract
- Show `/docs` (FastAPI auto-generated API docs)

**2:30–2:45 — Wrap-up**
- Mention extensibility: swappable DB, extendable skills taxonomy,
  batch scoring
