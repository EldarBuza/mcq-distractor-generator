import { useState } from 'react'
import type { GeneratedQuestion } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Check, RotateCcw, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

interface Props {
  results: GeneratedQuestion[]
}

/** Map an option string to the rationale of its distractor (correct answer has none). */
function rationaleFor(r: GeneratedQuestion, option: string): string | null {
  const di = r.distractors.indexOf(option)
  if (di === -1) return null
  return r.rationale[di] ?? null
}

/**
 * Interactive "take the quiz" view: the correct answer is hidden until the user
 * picks an option, then the card reveals which choice was right (and why the
 * chosen distractor was tempting). The fastest way to eyeball distractor quality.
 */
export function QuizView({ results }: Props) {
  // Selected option index per question, keyed by the question's index in `results`.
  const [selected, setSelected] = useState<Record<number, number>>({})

  // Reset all answers whenever a fresh set of results arrives. Adjusting state
  // during render (rather than in an effect) is React's recommended pattern for
  // resetting on a prop change — it avoids a wasted render with stale answers.
  const [prevResults, setPrevResults] = useState(results)
  if (results !== prevResults) {
    setPrevResults(results)
    setSelected({})
  }

  const quizzable = results.filter((r) => !r.error && r.options.length > 1).length
  const answeredIndices = Object.keys(selected).map(Number)
  const answered = answeredIndices.length
  const correct = answeredIndices.filter(
    (i) => selected[i] === results[i].correct_index,
  ).length

  function choose(qi: number, oi: number) {
    setSelected((prev) =>
      prev[qi] !== undefined ? prev : { ...prev, [qi]: oi },
    )
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Results</h2>
        <div className="flex items-center gap-3">
          {answered > 0 && (
            <Badge variant="secondary" className="tabular-nums">
              {correct} / {answered} correct
              {answered < quizzable && (
                <span className="text-muted-foreground">
                  {' '}
                  · {quizzable - answered} left
                </span>
              )}
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelected({})}
            disabled={answered === 0}
          >
            <RotateCcw className="size-3.5" />
            Reset
          </Button>
        </div>
      </div>

      {results.map((r, i) => {
        const choice = selected[i]
        const isAnswered = choice !== undefined

        return (
          <Card key={i}>
            <CardHeader className="space-y-1">
              <p className="font-medium leading-snug">
                {i + 1}. {r.question}
              </p>
            </CardHeader>
            <CardContent>
              {r.error ? (
                <p className="text-sm text-destructive">
                  Could not generate options: {r.error}
                </p>
              ) : (
                <ul className="space-y-2">
                  {r.options.map((opt, j) => {
                    const isCorrect = j === r.correct_index
                    const isChosen = choice === j
                    const showCorrect = isAnswered && isCorrect
                    const showWrong = isAnswered && isChosen && !isCorrect
                    const why = showWrong ? rationaleFor(r, opt) : null

                    return (
                      <li key={j}>
                        <button
                          type="button"
                          onClick={() => choose(i, j)}
                          disabled={isAnswered}
                          aria-pressed={isChosen}
                          className={cn(
                            'flex w-full gap-3 rounded-md border p-2.5 text-left text-sm transition-colors',
                            !isAnswered &&
                              'cursor-pointer hover:border-ring hover:bg-accent/50',
                            isAnswered && 'cursor-default',
                            showCorrect && 'border-green-500/50 bg-green-500/10',
                            showWrong && 'border-red-500/50 bg-red-500/10',
                            isAnswered &&
                              !showCorrect &&
                              !showWrong &&
                              'border-transparent opacity-60',
                            !isAnswered && 'border-input',
                          )}
                        >
                          <span
                            className={cn(
                              'flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-medium',
                              showCorrect
                                ? 'bg-green-600 text-white'
                                : showWrong
                                  ? 'bg-red-600 text-white'
                                  : 'bg-muted text-muted-foreground',
                            )}
                          >
                            {LETTERS[j] ?? j + 1}
                          </span>
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  (showCorrect || showWrong) && 'font-medium',
                                )}
                              >
                                {opt}
                              </span>
                              {showCorrect && (
                                <Check className="size-4 text-green-600" />
                              )}
                              {showWrong && <X className="size-4 text-red-600" />}
                            </div>
                            {why && (
                              <p className="text-xs text-muted-foreground">
                                {why}
                              </p>
                            )}
                          </div>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        )
      })}
    </section>
  )
}
