import { useEffect, useState } from 'react'
import { generate, getHealth } from '@/lib/api'
import type { GeneratedQuestion, HealthResponse, QuestionInput } from '@/types'
import { InputPanel } from '@/components/InputPanel'
import { QuestionEditorList } from '@/components/QuestionEditorList'
import { ResultsList } from '@/components/ResultsList'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Toaster } from '@/components/ui/sonner'
import { toast } from 'sonner'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [questions, setQuestions] = useState<QuestionInput[]>([])
  const [results, setResults] = useState<GeneratedQuestion[] | null>(null)
  // The exact inputs used for the current results, so a single card can be
  // regenerated with the same question/answer/difficulty/count.
  const [generatedInputs, setGeneratedInputs] = useState<QuestionInput[]>([])
  const [generating, setGenerating] = useState(false)
  const [regeneratingIndex, setRegeneratingIndex] = useState<number | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  function addQuestions(incoming: QuestionInput[]) {
    setQuestions((prev) => [...prev, ...incoming])
    toast.success(`Added ${incoming.length} question${incoming.length === 1 ? '' : 's'}`)
  }

  function updateQuestion(index: number, patch: Partial<QuestionInput>) {
    setQuestions((prev) =>
      prev.map((q, i) => (i === index ? { ...q, ...patch } : q)),
    )
  }

  function applyAll(patch: Partial<QuestionInput>) {
    setQuestions((prev) => prev.map((q) => ({ ...q, ...patch })))
  }

  async function handleGenerate() {
    const valid = questions.filter(
      (q) => q.question.trim() && q.correct_answer.trim(),
    )
    if (valid.length === 0) {
      toast.error('Add at least one question with an answer.')
      return
    }
    setGenerating(true)
    setResults(null)
    try {
      const resp = await generate(valid)
      setResults(resp.results)
      setGeneratedInputs(valid)
      const failed = resp.results.filter((r) => r.error).length
      if (failed) toast.warning(`${failed} question(s) could not be generated.`)
      else toast.success('Done!')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setGenerating(false)
    }
  }

  async function handleRegenerate(index: number) {
    const input = generatedInputs[index]
    if (!input) return
    setRegeneratingIndex(index)
    try {
      const resp = await generate([input])
      const fresh = resp.results[0]
      setResults((prev) =>
        prev ? prev.map((r, i) => (i === index ? fresh : r)) : prev,
      )
      if (fresh.error) toast.warning('Could not regenerate that question.')
      else toast.success('Regenerated.')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setRegeneratingIndex(null)
    }
  }

  const keyMissing = health !== null && !health.api_key_configured

  return (
    <div className="min-h-svh bg-background">
      <Toaster richColors position="top-center" />

      <header className="border-b">
        <div className="mx-auto max-w-3xl px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">MCQ Distractor Generator</h1>
            <p className="text-xs text-muted-foreground">
              Turn questions + answers into multiple-choice items.
            </p>
          </div>
          {health && (
            <Badge variant={health.api_key_configured ? 'secondary' : 'destructive'}>
              {health.api_key_configured ? health.model : 'no API key'}
            </Badge>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-6 space-y-6">
        {keyMissing && (
          <p className="text-sm text-destructive">
            The backend has no API key configured. Set ANTHROPIC_API_KEY in
            backend/.env and restart it.
          </p>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add questions</CardTitle>
          </CardHeader>
          <CardContent>
            <InputPanel onAdd={addQuestions} onError={(m) => toast.error(m)} />
          </CardContent>
        </Card>

        <QuestionEditorList
          questions={questions}
          onChange={updateQuestion}
          onRemove={(i) => setQuestions((prev) => prev.filter((_, j) => j !== i))}
          onClear={() => setQuestions([])}
          onApplyAll={applyAll}
        />

        {questions.length > 0 && (
          <div className="sticky bottom-4 flex justify-end">
            <Button size="lg" onClick={handleGenerate} disabled={generating}>
              {generating ? 'Generating…' : `Generate ${questions.length} MCQ${questions.length === 1 ? '' : 's'}`}
            </Button>
          </div>
        )}

        {results && (
          <ResultsList
            results={results}
            regeneratingIndex={regeneratingIndex}
            onRegenerate={handleRegenerate}
          />
        )}
      </main>
    </div>
  )
}

export default App
