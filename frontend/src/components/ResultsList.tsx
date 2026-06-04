import { useState } from 'react'
import type { GeneratedQuestion, KeptDistractor } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Download,
  Lock,
  LockOpen,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { exportAiken, exportCsv, exportGift, exportJson } from '@/lib/export'
import { detectIssues } from '@/lib/quality'

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
  onRegenerate: (index: number, keep: KeptDistractor[]) => void
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

  // Locked distractor texts per question index. Locked distractors are kept
  // verbatim when that question is regenerated; the rest are rerolled.
  const [locked, setLocked] = useState<Record<number, string[]>>({})

  const isLocked = (qi: number, text: string) =>
    (locked[qi] ?? []).includes(text)

  function toggleLock(qi: number, text: string) {
    setLocked((prev) => {
      const cur = prev[qi] ?? []
      return {
        ...prev,
        [qi]: cur.includes(text)
          ? cur.filter((t) => t !== text)
          : [...cur, text],
      }
    })
  }

  function regenerate(qi: number, r: GeneratedQuestion) {
    const lockedTexts = locked[qi] ?? []
    const keep: KeptDistractor[] = r.distractors
      .filter((d) => lockedTexts.includes(d))
      .map((d) => ({ text: d, rationale: rationaleFor(r, d) ?? '' }))
    onRegenerate(qi, keep)
  }

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
      {results.map((r, i) => {
        const issues = detectIssues(r)
        const issueFor = (j: number) => issues.find((it) => it.index === j)
        return (
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
                {issues.length > 0 && (
                  <Badge
                    variant="outline"
                    className="gap-1 border-amber-500/50 text-amber-700 dark:text-amber-500"
                  >
                    <AlertTriangle className="size-3" />
                    {issues.length} possible issue{issues.length === 1 ? '' : 's'}
                  </Badge>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => regenerate(i, r)}
              disabled={regeneratingIndex !== null}
            >
              <RefreshCw
                className={cn(
                  'size-3.5',
                  regeneratingIndex === i && 'animate-spin',
                )}
              />
              {(locked[i]?.length ?? 0) > 0 ? 'Reroll unlocked' : 'Regenerate'}
            </Button>
          </CardHeader>
          <CardContent>
            {r.answer_check && !r.answer_check.ok && (
              <div className="mb-3 flex gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 p-2.5 text-sm">
                <AlertTriangle className="size-4 shrink-0 text-amber-600" />
                <div>
                  <span className="font-medium">This answer may be incorrect.</span>
                  {r.answer_check.note && (
                    <span className="text-muted-foreground"> {r.answer_check.note}</span>
                  )}
                </div>
              </div>
            )}
            {r.error ? (
              <p className="text-sm text-destructive">
                Could not generate options: {r.error}
              </p>
            ) : (
              <ul className="space-y-2">
                {r.options.map((opt, j) => {
                  const isCorrect = j === r.correct_index
                  const why = isCorrect ? null : rationaleFor(r, opt)
                  const kept = !isCorrect && isLocked(i, opt)
                  const issue = isCorrect ? undefined : issueFor(j)
                  return (
                    <li
                      key={j}
                      className={cn(
                        'flex items-start gap-3 rounded-md border p-2.5 text-sm',
                        isCorrect
                          ? 'border-green-500/50 bg-green-500/10'
                          : kept
                            ? 'border-primary/40 bg-primary/5'
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
                          <span
                            className={cn((isCorrect || kept) && 'font-medium')}
                          >
                            {opt}
                          </span>
                          {isCorrect && (
                            <Check className="size-4 text-green-600" />
                          )}
                        </div>
                        {why && (
                          <p className="text-xs text-muted-foreground">{why}</p>
                        )}
                        {issue && (
                          <p className="flex items-center gap-1 text-xs text-amber-600">
                            <AlertTriangle className="size-3 shrink-0" />
                            {issue.message}
                          </p>
                        )}
                      </div>
                      {!isCorrect && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="ml-auto size-7 shrink-0"
                          aria-label={
                            kept
                              ? 'Unlock distractor (will be rerolled)'
                              : 'Lock distractor (keep on regenerate)'
                          }
                          aria-pressed={kept}
                          title={
                            kept
                              ? 'Locked — kept when you regenerate'
                              : 'Lock to keep this on regenerate'
                          }
                          disabled={regeneratingIndex !== null}
                          onClick={() => toggleLock(i, opt)}
                        >
                          {kept ? (
                            <Lock className="size-3.5 text-primary" />
                          ) : (
                            <LockOpen className="size-3.5 text-muted-foreground" />
                          )}
                        </Button>
                      )}
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
