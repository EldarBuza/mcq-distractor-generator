# Backend — MCQ Distractor Generator

FastAPI service that generates plausible-but-wrong MCQ answer choices with Claude.

## Setup

```powershell
# from repo root
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# configure your key (this file is gitignored)
Copy-Item backend\.env.example backend\.env
# then edit backend\.env and paste your ANTHROPIC_API_KEY
```

## Run (dev)

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Then open http://127.0.0.1:8000/health

## Test

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
```

## Endpoints

| Method | Path        | Description                                          |
|--------|-------------|------------------------------------------------------|
| GET    | `/health`   | Liveness + whether an API key is configured.         |
| POST   | `/generate` | Generate distractors for a batch of questions.       |

### POST `/generate`

Request:

```jsonc
{
  "questions": [
    { "question": "Capital of Japan?", "correct_answer": "Tokyo",
      "num_distractors": 3, "difficulty": "easy" }
  ]
}
```

Response: `{ "results": [ { question, correct_answer, options, correct_index,
distractors, rationale, difficulty, error } ] }`. Results line up 1:1 with the
input order. A per-question failure sets `error` instead of failing the batch.
Returns `503` if no API key is configured on the server.
