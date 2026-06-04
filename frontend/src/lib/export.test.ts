import { describe, expect, it } from 'vitest'
import { toCsv, toGift } from './export'
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
