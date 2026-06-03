// Client-side exporters for generated MCQs: CSV and GIFT (Moodle/LMS import).
import type { GeneratedQuestion } from '@/types'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

function usable(results: GeneratedQuestion[]): GeneratedQuestion[] {
  // Exclude questions that failed to generate (only the correct answer present).
  return results.filter((r) => !r.error && r.options.length > 1)
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
