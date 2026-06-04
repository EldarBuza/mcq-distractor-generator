import { describe, expect, it } from 'vitest'
import { detectIssues } from './quality'
import type { GeneratedQuestion } from '@/types'

function q(overrides: Partial<GeneratedQuestion> = {}): GeneratedQuestion {
  return {
    question: 'Capital of Japan?',
    correct_answer: 'Tokyo',
    options: ['Kyoto', 'Tokyo', 'Osaka'],
    correct_index: 1,
    distractors: ['Kyoto', 'Osaka'],
    rationale: [],
    misconceptions: [],
    difficulty: 'medium',
    error: null,
    verified: false,
    answer_check: null,
    ...overrides,
  }
}

describe('detectIssues', () => {
  it('returns nothing for clean, distinct options', () => {
    expect(detectIssues(q())).toEqual([])
  })

  it('flags giveaway phrasings', () => {
    const issues = detectIssues(
      q({
        options: ['Kyoto', 'Tokyo', 'All of the above'],
        correct_index: 1,
      }),
    )
    expect(issues).toHaveLength(1)
    expect(issues[0]).toMatchObject({ index: 2, kind: 'giveaway' })
  })

  it('flags a distractor that overlaps the correct answer (extra words)', () => {
    const issues = detectIssues(
      q({
        options: ['Tokyo, Japan', 'Tokyo', 'Osaka'],
        correct_index: 1,
      }),
    )
    expect(issues).toEqual([
      { index: 0, kind: 'overlaps-answer', message: expect.any(String) },
    ])
  })

  it('flags a distractor that only differs from the answer by punctuation/case', () => {
    const issues = detectIssues(
      q({ options: ['tokyo.', 'Tokyo', 'Osaka'], correct_index: 1 }),
    )
    expect(issues.map((i) => i.kind)).toEqual(['overlaps-answer'])
  })

  it('flags near-duplicate distractors once, on the later option', () => {
    const issues = detectIssues(
      q({
        options: ['Tokyo', 'Mount Fuji', 'mount fuji!', 'Osaka'],
        correct_index: 0,
      }),
    )
    expect(issues).toEqual([
      { index: 2, kind: 'overlaps-option', message: expect.any(String) },
    ])
  })

  it('never flags the correct answer itself and ignores errored questions', () => {
    expect(
      detectIssues(q({ error: 'boom', options: ['Tokyo'], correct_index: 0 })),
    ).toEqual([])
    // A correct answer containing a common word does not trip option overlap.
    expect(
      detectIssues(
        q({
          correct_answer: 'The cell',
          options: ['The nucleus', 'The cell', 'The ribosome'],
          correct_index: 1,
        }),
      ),
    ).toEqual([])
  })
})
