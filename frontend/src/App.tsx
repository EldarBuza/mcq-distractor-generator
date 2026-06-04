import { useEffect, useRef, useState } from 'react'
import { generate, getHealth } from '@/lib/api'
import type { GeneratedQuestion, HealthResponse, QuestionInput } from '@/types'
import { InputPanel } from '@/components/InputPanel'
import { QuestionEditorList } from '@/components/QuestionEditorList'
import { ResultsList } from '@/components/ResultsList'
import { QuizView } from '@/components/QuizView'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Toaster } from '@/components/ui/sonner'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import { usePersistentState } from '@/lib/usePersistentState'

type ResultsView = 'key' | 'quiz'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  // Persisted across reloads so a refresh never discards in-progress work.
  const [questions, setQuestions] = usePersistentState<QuestionInput[]>(
    'mcq.questions',
    [],
  )
  const [results, setResults] = usePersistentState<GeneratedQuestion[] | null>(
    'mcq.results',
    null,
  )
  // The exact inputs used for the current results, so a single card can be
  // regenerated with the same question/answer/difficulty/count.
  const [generatedInputs, setGeneratedInputs] = usePersistentState<
    QuestionInput[]
  >('mcq.generatedInputs', [])
  // Optional second LLM pass that critiques and prunes weak distractors.
  const [verify, setVerify] = usePersistentState('mcq.verify', false)
  const [generating, setGenerating] = useState(false)
  const [regeneratingIndex, setRegeneratingIndex] = useState<number | null>(null)
  const [resultsView, setResultsView] = useState<ResultsView>('key')
  const resultsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  // Bring fresh results into view once they render — but not on the initial
  // mount, where results may have just been restored from localStorage and an
  // auto-scroll would be jarring.
  const didMount = useRef(false)
  useEffect(() => {
    if (!didMount.current) {
      didMount.current = true
      return
    }
    if (results) resultsRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [results])

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
      const resp = await generate(valid, verify)
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
      const resp = await generate([input], verify)
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
          <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background/80 px-4 py-3 shadow-lg backdrop-blur">
            <label className="flex items-center gap-2 cursor-pointer">
              <Switch
                checked={verify}
                onCheckedChange={setVerify}
                disabled={generating}
                aria-label="Verify distractors"
              />
              <span className="text-sm leading-tight">
                <span className="font-medium">Verify distractors</span>
                <span className="block text-xs text-muted-foreground">
                  Extra AI review pass — slower &amp; higher cost, better quality
                </span>
              </span>
            </label>
            <Button
              size="lg"
              onClick={handleGenerate}
              disabled={generating || keyMissing}
            >
              {generating && <Loader2 className="size-4 animate-spin" />}
              {generating
                ? 'Generating…'
                : `Generate ${questions.length} MCQ${questions.length === 1 ? '' : 's'}`}
            </Button>
          </div>
        )}

        <div ref={resultsRef} className="scroll-mt-6 space-y-4">
          {generating && <ResultsSkeleton count={questions.length} />}
          {!generating && results && results.length > 0 && (
            <>
              <div className="flex justify-end">
                <Tabs
                  value={resultsView}
                  onValueChange={(v) => setResultsView(v as ResultsView)}
                >
                  <TabsList>
                    <TabsTrigger value="key">Answer key</TabsTrigger>
                    <TabsTrigger value="quiz">Take quiz</TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
              {resultsView === 'key' ? (
                <ResultsList
                  results={results}
                  regeneratingIndex={regeneratingIndex}
                  onRegenerate={handleRegenerate}
                />
              ) : (
                <QuizView results={results} />
              )}
            </>
          )}
        </div>
      </main>

      <footer className="border-t mt-10">
        <div className="mx-auto max-w-3xl px-6 py-4 text-xs text-muted-foreground">
          The answer you provide always stays the correct option — distractors
          are generated around it and shuffled.
        </div>
      </footer>
    </div>
  )
}

function ResultsSkeleton({ count }: { count: number }) {
  const cards = Math.min(count, 4)
  return (
    <section className="space-y-4" aria-label="Generating results">
      <h2 className="text-base font-semibold">Results</h2>
      {Array.from({ length: cards }).map((_, i) => (
        <div key={i} className="rounded-xl border p-4 space-y-3">
          <div className="h-4 w-2/3 rounded bg-muted animate-pulse" />
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, j) => (
              <div key={j} className="h-9 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}

export default App
