// Mirrors the backend Pydantic schemas (app/models.py).

export type Difficulty = 'easy' | 'medium' | 'hard'

export interface QuestionInput {
  question: string
  correct_answer: string
  num_distractors: number
  difficulty: Difficulty
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
}

export interface GenerateResponse {
  results: GeneratedQuestion[]
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
