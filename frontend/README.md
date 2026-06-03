# Frontend — MCQ Distractor Generator

React + Vite + TypeScript + Tailwind v4 + shadcn/ui.

## Setup

```powershell
cd frontend
npm install
```

## Run (dev)

The backend should be running on port 8000 (see `../backend/README.md`).
The Vite dev server proxies `/api/*` to it, so there are no CORS concerns.

```powershell
cd frontend
npm run dev
```

Open the printed URL (default http://localhost:5173).

## Scripts

| Command           | Description                               |
|-------------------|-------------------------------------------|
| `npm run dev`     | Start the dev server (with `/api` proxy). |
| `npm run build`   | Type-check and build to `dist/`.          |
| `npm run lint`    | Run ESLint.                               |
| `npm run preview` | Preview the production build.             |

## Structure

- `src/lib/api.ts` — typed client; all calls go through `/api`.
- `src/types.ts` — types mirroring the backend schemas.
- `src/components/ui/` — generated shadcn/ui primitives.
