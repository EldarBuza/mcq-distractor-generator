// Mirrors the backend Pydantic schemas (app/models.py).

export type Difficulty = 'easy' | 'medium' | 'hard'

export interface QuestionInput {
  question: string
  correct_answer: string
  num_distractors: number
  difficulty: Difficulty
}

// Advisory verdict on whether the supplied correct answer is actually correct.
export interface AnswerCheck {
  ok: boolean
  note: string
}

export interface GeneratedQuestion {
  question: string
  correct_answer: string
  options: string[]
  correct_index: number
  distractors: string[]
  rationale: string[]
  difficulty: Difficulty
  error: string | null
  verified: boolean
  answer_check: AnswerCheck | null
}

export interface GenerateResponse {
  results: GeneratedQuestion[]
}

// Status of an asynchronous "economy" batch generation job.
export interface BatchStatus {
  batch_id: string
  status: string
  done: boolean
  succeeded: number
  errored: number
  total: number
  results: GeneratedQuestion[] | null
}

// A distractor the user locked, sent back so it survives a partial regenerate.
export interface KeptDistractor {
  text: string
  rationale: string
}

export interface ParseResult {
  questions: QuestionInput[]
  errors: string[]
}

export interface HealthResponse {
  status: string
  model: string
  api_key_configured: boolean
}
