// Client-side exporters for generated MCQs: CSV and GIFT (Moodle/LMS import).
import type { GeneratedQuestion } from '@/types'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

/** The option label for index i: A, B, C, … and beyond F if ever needed. */
function letter(i: number): string {
  return LETTERS[i] ?? String.fromCharCode(65 + i)
}

function usable(results: GeneratedQuestion[]): GeneratedQuestion[] {
  // Exclude questions that failed to generate (only the correct answer present).
  return results.filter((r) => !r.error && r.options.length > 1)
}

/** Collapse internal line breaks to single spaces (for one-line-per-field formats). */
function oneLine(value: string): string {
  return value.replace(/\s*[\r\n]+\s*/g, ' ').trim()
}

// ---- CSV --------------------------------------------------------------------

function csvCell(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

/** Columns: #, Question, Difficulty, Correct answer, Answer key, A, B, C, ... */
export function toCsv(results: GeneratedQuestion[]): string {
  const rows = usable(results)
  const maxOptions = rows.reduce((m, r) => Math.max(m, r.options.length), 0)

  const header = ['#', 'Question', 'Difficulty', 'Correct answer', 'Answer key']
  for (let i = 0; i < maxOptions; i++) header.push(LETTERS[i] ?? `Option ${i + 1}`)

  const lines = [header.map(csvCell).join(',')]
  rows.forEach((r, idx) => {
    const cells = [
      String(idx + 1),
      r.question,
      r.difficulty,
      r.correct_answer,
      LETTERS[r.correct_index] ?? String(r.correct_index + 1),
      ...r.options,
    ]
    // Pad option columns so every row has the same width.
    while (cells.length < header.length) cells.push('')
    lines.push(cells.map(csvCell).join(','))
  })

  return lines.join('\r\n')
}

// ---- GIFT (Moodle) ----------------------------------------------------------

// In GIFT, ~ = # { } : and \ are control characters and must be escaped.
function giftEscape(value: string): string {
  return value.replace(/([~=#{}:\\])/g, '\\$1')
}

export function toGift(results: GeneratedQuestion[]): string {
  return usable(results)
    .map((r, i) => {
      const body = r.options
        .map((opt, j) =>
          j === r.correct_index
            ? `\t=${giftEscape(opt)}`
            : `\t~${giftEscape(opt)}`,
        )
        .join('\n')
      return `::Question ${i + 1}::${giftEscape(r.question)} {\n${body}\n}`
    })
    .join('\n\n')
}

// ---- Aiken ------------------------------------------------------------------

// Aiken is a plain-text MCQ format importable by Moodle and many other tools.
// Each question is a single line, followed by "A. option" lines and an
// "ANSWER: <LETTER>" line. The format has no escaping, and questions/options
// must each fit on one line — so internal line breaks are collapsed.
export function toAiken(results: GeneratedQuestion[]): string {
  return usable(results)
    .map((r) => {
      const lines = [oneLine(r.question)]
      r.options.forEach((opt, j) => lines.push(`${letter(j)}. ${oneLine(opt)}`))
      lines.push(`ANSWER: ${letter(r.correct_index)}`)
      return lines.join('\n')
    })
    .join('\n\n')
}

// ---- JSON -------------------------------------------------------------------

/** A clean, re-importable projection of each MCQ (drops transient fields). */
export function toJson(results: GeneratedQuestion[]): string {
  const items = usable(results).map((r) => ({
    question: r.question,
    options: r.options,
    correct_answer: r.correct_answer,
    correct_index: r.correct_index,
    difficulty: r.difficulty,
    rationale: r.rationale,
  }))
  return JSON.stringify(items, null, 2)
}

// ---- download helper --------------------------------------------------------

export function downloadText(
  filename: string,
  contents: string,
  mime: string,
): void {
  const blob = new Blob([contents], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function exportCsv(results: GeneratedQuestion[]): void {
  downloadText('mcqs.csv', toCsv(results), 'text/csv')
}

export function exportGift(results: GeneratedQuestion[]): void {
  downloadText('mcqs.gift.txt', toGift(results), 'text/plain')
}

export function exportAiken(results: GeneratedQuestion[]): void {
  downloadText('mcqs.aiken.txt', toAiken(results), 'text/plain')
}

export function exportJson(results: GeneratedQuestion[]): void {
  downloadText('mcqs.json', toJson(results), 'application/json')
}
