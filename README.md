# MCQ Distractor Generator

Turn `(question, correct_answer)` pairs into multiple-choice questions. AI
generates plausible-but-wrong answer choices (distractors) while your supplied
answer always remains THE correct one.

- **Backend:** FastAPI + Anthropic SDK (Claude Haiku 4.5)
- **Frontend:** React + Vite + TypeScript + Tailwind + shadcn/ui
- **Export:** CSV and GIFT (Moodle/LMS import)

The correct answer is assembled in code (never asked of the model) and the
options are shuffled server-side, so the user's answer is guaranteed to survive
verbatim and appear exactly once.

## Quick start (Docker)

1. Provide your API key (kept on your machine, never committed):
   ```powershell
   Copy-Item backend\.env.example backend\.env
   # edit backend\.env and paste your ANTHROPIC_API_KEY
   ```
2. Build and run:
   ```powershell
   docker compose up --build
   ```
3. Open http://localhost:8080

The key is read at runtime from `backend/.env` via compose `env_file` — it is
never baked into an image layer. nginx serves the frontend and proxies `/api/*`
to the backend, so there is no CORS configuration to worry about.

## Local development (without Docker)

Run the two services in separate terminals:

```powershell
# Terminal 1 — backend (http://127.0.0.1:8000)
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # then add your key
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to the backend on port 8000.

## Tests

```powershell
# backend
cd backend; .venv\Scripts\python.exe -m pytest -q

# frontend
cd frontend; npm test
```

## Input formats

- **Paste:** one `question | answer` per line (tab or `;` also work), or paste
  CSV / JSON directly.
- **Upload:** `.csv` (`question,correct_answer[,num_distractors,difficulty]`),
  `.json` (a list or `{ "questions": [...] }`), `.tsv`, `.txt`.

See `backend/samples/questions.csv` for an example.

## Project layout

```
backend/    FastAPI app, generator, parsing, tests
frontend/   Vite React app, components, API client, tests
docker-compose.yml
PLAN.md     build plan / progress checklist
```
