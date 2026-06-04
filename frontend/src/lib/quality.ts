// Heuristic, client-side "dud" detection for generated options. Free and
// instant — it complements the optional (paid) LLM verify pass by catching
// mechanical problems deterministically: giveaway phrases, and distractors that
// overlap the correct answer or each other beyond the backend's exact-match
// dedupe (which ignores punctuation/extra words).
import type { GeneratedQuestion } from '@/types'

export type IssueKind = 'giveaway' | 'overlaps-answer' | 'overlaps-option'

export interface OptionIssue {
  /** Index into the question's `options` array. */
  index: number
  kind: IssueKind
  message: string
}

// Classic "this is a giveaway / non-distractor" phrasings.
const GIVEAWAY =
  /\b(all|none|both)\s+of\s+(the\s+)?(above|following|these|them)\b|\ball\s+of\s+these\b/i

/** Lowercase, strip punctuation, collapse whitespace. */
function normalizeLoose(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function tokenSet(s: string): Set<string> {
  return new Set(normalizeLoose(s).split(' ').filter(Boolean))
}

function isSubset(a: Set<string>, b: Set<string>): boolean {
  if (a.size === 0) return false
  for (const t of a) if (!b.has(t)) return false
  return true
}

/**
 * Two option strings "overlap" if, ignoring case/punctuation, they are equal or
 * one's words are a subset of the other's (e.g. "Tokyo" vs "Tokyo, Japan").
 * A single shared common word (e.g. "the") is not enough on its own.
 */
function overlaps(a: string, b: string): boolean {
  const ta = tokenSet(a)
  const tb = tokenSet(b)
  if (ta.size === 0 || tb.size === 0) return false
  return isSubset(ta, tb) || isSubset(tb, ta)
}

/**
 * Detect likely-dud options in a finished question. Returns one issue per
 * affected option (an option may appear once); the correct answer is never
 * itself flagged, only distractors that collide with it. Errored questions and
 * trivial single-option results yield nothing.
 */
export function detectIssues(r: GeneratedQuestion): OptionIssue[] {
  if (r.error || r.options.length < 2) return []

  const issues: OptionIssue[] = []
  const correct = r.options[r.correct_index]

  r.options.forEach((opt, i) => {
    if (i === r.correct_index) return

    if (GIVEAWAY.test(opt)) {
      issues.push({
        index: i,
        kind: 'giveaway',
        message: 'Reads like a giveaway, not a real distractor.',
      })
      return // one issue per option is enough to prompt a fix
    }

    if (overlaps(opt, correct)) {
      issues.push({
        index: i,
        kind: 'overlaps-answer',
        message: 'Too similar to the correct answer.',
      })
      return
    }

    // Compare against earlier distractors only, so a colliding pair is flagged
    // once (on the later option).
    for (let j = 0; j < i; j++) {
      if (j === r.correct_index) continue
      if (overlaps(opt, r.options[j])) {
        issues.push({
          index: i,
          kind: 'overlaps-option',
          message: 'Nearly duplicates another option.',
        })
        return
      }
    }
  })

  return issues
}
