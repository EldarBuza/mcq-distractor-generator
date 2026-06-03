// Typed client for the FastAPI backend.
// All calls go through "/api", which Vite proxies to the backend in dev and
// nginx proxies in the Docker build — so there is never a CORS concern.
import type {
  GenerateResponse,
  HealthResponse,
  ParseResult,
  QuestionInput,
} from '@/types'

const BASE = '/api'

async function asJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`
    try {
      const body = await resp.json()
      if (body?.detail) detail = body.detail
    } catch {
      // non-JSON error body; keep the default message
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<T>
}

export async function getHealth(): Promise<HealthResponse> {
  return asJson<HealthResponse>(await fetch(`${BASE}/health`))
}

export async function generate(
  questions: QuestionInput[],
): Promise<GenerateResponse> {
  const resp = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ questions }),
  })
  return asJson<GenerateResponse>(resp)
}

export async function parseFile(file: File): Promise<ParseResult> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${BASE}/parse`, { method: 'POST', body: form })
  return asJson<ParseResult>(resp)
}
