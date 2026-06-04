import type { GeneratedQuestion } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Check, ChevronDown, Download, RefreshCw, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'
import { exportAiken, exportCsv, exportGift, exportJson } from '@/lib/export'

const EXPORTS: { label: string; run: (r: GeneratedQuestion[]) => void }[] = [
  { label: 'CSV (spreadsheet)', run: exportCsv },
  { label: 'GIFT (Moodle)', run: exportGift },
  { label: 'Aiken (LMS import)', run: exportAiken },
  { label: 'JSON', run: exportJson },
]

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

const DIFFICULTY_VARIANT: Record<
  GeneratedQuestion['difficulty'],
  'secondary' | 'default' | 'destructive'
> = {
  easy: 'secondary',
  medium: 'default',
  hard: 'destructive',
}

interface Props {
  results: GeneratedQuestion[]
  regeneratingIndex: number | null
  onRegenerate: (index: number) => void
}

/** Map each option to the rationale of its distractor (correct answer has none). */
function rationaleFor(r: GeneratedQuestion, option: string): string | null {
  const di = r.distractors.indexOf(option)
  if (di === -1) return null
  return r.rationale[di] ?? null
}

export function ResultsList({
  results,
  regeneratingIndex,
  onRegenerate,
}: Props) {
  const exportable = results.filter((r) => !r.error && r.options.length > 1).length

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Results</h2>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={exportable === 0}>
              <Download className="size-3.5" />
              Export
              <ChevronDown className="size-3.5 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {EXPORTS.map(({ label, run }) => (
              <DropdownMenuItem key={label} onSelect={() => run(results)}>
                {label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {results.map((r, i) => (
        <Card key={i}>
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div className="space-y-1">
              <p className="font-medium leading-snug">
                {i + 1}. {r.question}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={DIFFICULTY_VARIANT[r.difficulty]} className="capitalize">
                  {r.difficulty}
                </Badge>
                {r.verified && !r.error && (
                  <Badge variant="secondary" className="gap-1">
                    <ShieldCheck className="size-3" />
                    Verified
                  </Badge>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onRegenerate(i)}
              disabled={regeneratingIndex !== null}
            >
              <RefreshCw
                className={cn(
                  'size-3.5',
                  regeneratingIndex === i && 'animate-spin',
                )}
              />
              Regenerate
            </Button>
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
                  const why = isCorrect ? null : rationaleFor(r, opt)
                  return (
                    <li
                      key={j}
                      className={cn(
                        'flex gap-3 rounded-md border p-2.5 text-sm',
                        isCorrect
                          ? 'border-green-500/50 bg-green-500/10'
                          : 'border-transparent',
                      )}
                    >
                      <span
                        className={cn(
                          'flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-medium',
                          isCorrect
                            ? 'bg-green-600 text-white'
                            : 'bg-muted text-muted-foreground',
                        )}
                      >
                        {LETTERS[j] ?? j + 1}
                      </span>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className={cn(isCorrect && 'font-medium')}>
                            {opt}
                          </span>
                          {isCorrect && (
                            <Check className="size-4 text-green-600" />
                          )}
                        </div>
                        {why && (
                          <p className="text-xs text-muted-foreground">{why}</p>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      ))}
    </section>
  )
}
