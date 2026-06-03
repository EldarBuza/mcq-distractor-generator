# MCQ Distractor Generator — Plan

An app that takes `(question, correct_answer)` pairs and uses AI to generate
plausible-but-wrong answer choices (distractors), keeping the user's answer as
THE correct answer.

## Stack
- **Backend:** FastAPI + Anthropic SDK (Claude Haiku 4.5), Pydantic
- **Frontend:** React + Vite + TypeScript + Tailwind + shadcn/ui
- **Model:** `claude-haiku-4-5-20251001` (configurable via env)
- **Packaging:** Docker + docker-compose (`docker compose up` runs both services)

## Core design rule
Never ask the model to include the correct answer. Ask only for N *wrong*
options, then assemble `[correct] + distractors`, shuffle server-side, and record
`correct_index`. The correct-answer guarantee is enforced in code, not the prompt.

## Build order
- [x] 1. Backend skeleton (FastAPI app, config, `/health`, venv + deps)
- [x] 2. Schemas + prompt (`models.py`, `prompts.py` with few-shot)
- [x] 3. Core generator (single question vs real API)
- [x] 4. `/generate` endpoint (batch, concurrency, error handling)
- [x] 5. Input parsing (CSV + JSON + paste)
- [x] 6. Frontend scaffold (Vite+TS+Tailwind+shadcn, talks to `/health`)
- [ ] 7. Input UI (paste + file upload + options)
- [ ] 8. Results UI (question cards, highlight correct, regenerate-one)
- [ ] 9. Export (CSV; GIFT/Moodle optional)
- [ ] 10. Dockerize (backend Dockerfile, frontend multi-stage + nginx, docker-compose, .dockerignore)
- [ ] 11. Polish (loading/error/empty states, rate-limit handling)

## Defaults (override anytime)
- Input: paste-in + CSV (`question,correct_answer`) + JSON. `.docx` deferred.
- Distractors: default 3, adjustable 1–5.
- Difficulty: easy | medium | hard.
- Export: CSV first; GIFT/Moodle XML later.
- Self-critique pass: built but off by default (toggle); ~doubles cost.
- Auth/persistence: none in v1 (stateless, no DB).
- Secrets: `ANTHROPIC_API_KEY` in `backend/.env` (gitignored). User supplies it.
- Docker: `.env` passed at runtime via compose `env_file:` — never baked into an
  image layer. Local dev (uvicorn + vite) stays fully supported alongside Docker.
- Frontend container: nginx serves the built bundle and proxies `/api` -> backend,
  so CORS is a non-issue in the dockerized setup.

## Cost/quality measures
- Prompt caching on the system block (rules + few-shot are identical per request).
- `asyncio.gather` with a semaphore to fan out batches concurrently.
- Optional Batches API for large file uploads (~50% cheaper, non-realtime).
