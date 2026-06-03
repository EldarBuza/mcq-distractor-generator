import type { Difficulty, QuestionInput } from '@/types'
import { DIFFICULTIES, DISTRACTOR_COUNTS } from '@/lib/constants'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Trash2 } from 'lucide-react'

interface Props {
  questions: QuestionInput[]
  onChange: (index: number, patch: Partial<QuestionInput>) => void
  onRemove: (index: number) => void
  onClear: () => void
  onApplyAll: (patch: Partial<QuestionInput>) => void
}

export function QuestionEditorList({
  questions,
  onChange,
  onRemove,
  onClear,
  onApplyAll,
}: Props) {
  if (questions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No questions yet. Add some above to get started.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm font-medium">
          {questions.length} question{questions.length === 1 ? '' : 's'}
        </span>
        <div className="flex items-center gap-2">
          <Select
            onValueChange={(v) => onApplyAll({ difficulty: v as Difficulty })}
          >
            <SelectTrigger size="sm" className="w-[150px]">
              <SelectValue placeholder="Set all difficulty" />
            </SelectTrigger>
            <SelectContent>
              {DIFFICULTIES.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            onValueChange={(v) => onApplyAll({ num_distractors: Number(v) })}
          >
            <SelectTrigger size="sm" className="w-[150px]">
              <SelectValue placeholder="Set all #" />
            </SelectTrigger>
            <SelectContent>
              {DISTRACTOR_COUNTS.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n} distractors
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear all
          </Button>
        </div>
      </div>

      <ul className="space-y-3">
        {questions.map((q, i) => (
          <li
            key={i}
            className="rounded-lg border p-4 space-y-3 bg-card"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 space-y-2">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Question</Label>
                  <Input
                    value={q.question}
                    onChange={(e) => onChange(i, { question: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">
                    Correct answer
                  </Label>
                  <Input
                    value={q.correct_answer}
                    onChange={(e) =>
                      onChange(i, { correct_answer: e.target.value })
                    }
                  />
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove question"
                onClick={() => onRemove(i)}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <Select
                value={q.difficulty}
                onValueChange={(v) => onChange(i, { difficulty: v as Difficulty })}
              >
                <SelectTrigger size="sm" className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DIFFICULTIES.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={String(q.num_distractors)}
                onValueChange={(v) => onChange(i, { num_distractors: Number(v) })}
              >
                <SelectTrigger size="sm" className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DISTRACTOR_COUNTS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n} distractors
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
