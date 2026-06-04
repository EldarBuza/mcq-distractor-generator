import { describe, expect, it } from 'vitest'
import { toAiken, toCsv, toGift, toJson } from './export'
import type { GeneratedQuestion } from '@/types'

function q(overrides: Partial<GeneratedQuestion> = {}): GeneratedQuestion {
  return {
    question: 'Capital of France?',
    correct_answer: 'Paris',
    options: ['London', 'Paris', 'Rome'],
    correct_index: 1,
    distractors: ['London', 'Rome'],
    rationale: [],
    difficulty: 'medium',
    error: null,
    verified: false,
    answer_check: null,
    ...overrides,
  }
}

describe('toCsv', () => {
  it('emits a header and one row per usable question', () => {
    const csv = toCsv([q()])
    const lines = csv.split('\r\n')
    expect(lines[0]).toBe('#,Question,Difficulty,Correct answer,Answer key,A,B,C')
    expect(lines[1]).toBe('1,Capital of France?,medium,Paris,B,London,Paris,Rome')
  })

  it('quotes cells containing commas or quotes', () => {
    const csv = toCsv([
      q({ question: 'A, B or C?', correct_answer: 'say "hi"', options: ['x', 'say "hi"'], correct_index: 1 }),
    ])
    expect(csv).toContain('"A, B or C?"')
    expect(csv).toContain('"say ""hi"""')
  })

  it('pads option columns so rows are rectangular', () => {
    const csv = toCsv([
      q({ options: ['a', 'b', 'c', 'd', 'e'], correct_index: 0 }),
      q({ options: ['x', 'y'], correct_index: 0 }),
    ])
    const lines = csv.split('\r\n')
    const cols = lines[0].split(',').length
    expect(lines[1].split(',').length).toBe(cols)
    expect(lines[2].split(',').length).toBe(cols)
  })

  it('excludes errored questions', () => {
    const csv = toCsv([q({ error: 'boom', options: ['Paris'] })])
    expect(csv.split('\r\n')).toHaveLength(1) // header only
  })
})

describe('toGift', () => {
  it('marks the correct answer with = and distractors with ~', () => {
    const gift = toGift([q()])
    expect(gift).toContain('=Paris')
    expect(gift).toContain('~London')
    expect(gift).toContain('~Rome')
    expect(gift).toContain('::Question 1::Capital of France?')
  })

  it('escapes GIFT control characters', () => {
    const gift = toGift([
      q({ question: 'What is {x}?', options: ['a=b', 'Paris'], correct_index: 1, correct_answer: 'Paris' }),
    ])
    expect(gift).toContain('What is \\{x\\}?')
    expect(gift).toContain('~a\\=b')
  })
})

describe('toAiken', () => {
  it('emits the question, lettered options, and an ANSWER line', () => {
    const aiken = toAiken([q()])
    expect(aiken).toBe(
      ['Capital of France?', 'A. London', 'B. Paris', 'C. Rome', 'ANSWER: B'].join(
        '\n',
      ),
    )
  })

  it('separates questions with a blank line', () => {
    const aiken = toAiken([q(), q({ question: 'Second?' })])
    expect(aiken).toContain('ANSWER: B\n\nSecond?')
  })

  it('collapses internal line breaks so each field stays on one line', () => {
    const aiken = toAiken([q({ question: 'Line one\nline two' })])
    expect(aiken.split('\n')[0]).toBe('Line one line two')
  })

  it('excludes errored questions', () => {
    expect(toAiken([q({ error: 'boom', options: ['Paris'] })])).toBe('')
  })
})

describe('toJson', () => {
  it('emits a re-importable projection without transient fields', () => {
    const data = JSON.parse(toJson([q()]))
    expect(data).toHaveLength(1)
    expect(data[0]).toEqual({
      question: 'Capital of France?',
      options: ['London', 'Paris', 'Rome'],
      correct_answer: 'Paris',
      correct_index: 1,
      difficulty: 'medium',
      rationale: [],
    })
    expect(data[0]).not.toHaveProperty('error')
    expect(data[0]).not.toHaveProperty('verified')
  })

  it('excludes errored questions', () => {
    expect(JSON.parse(toJson([q({ error: 'boom', options: ['Paris'] })]))).toEqual(
      [],
    )
  })
})
