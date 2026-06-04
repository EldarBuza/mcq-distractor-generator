import { useRef, useState } from 'react'
import { parseFile, parseText } from '@/lib/api'
import type { QuestionInput } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Upload } from 'lucide-react'

interface Props {
  onAdd: (questions: QuestionInput[]) => void
  onError: (message: string) => void
}

const PLACEHOLDER = `One question per line, e.g.

What is the capital of Japan? | Tokyo
Who wrote 'Hamlet'? | William Shakespeare

You can also paste CSV (question,correct_answer) or JSON.`

export function InputPanel({ onAdd, onError }: Props) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [text, setText] = useState('')
  const [parsing, setParsing] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const questionRef = useRef<HTMLInputElement>(null)

  function handleAddSingle() {
    if (!question.trim() || !answer.trim()) return
    onAdd([
      {
        question: question.trim(),
        correct_answer: answer.trim(),
        num_distractors: 3,
        difficulty: 'medium',
      },
    ])
    setQuestion('')
    setAnswer('')
    questionRef.current?.focus()
  }

  function report(result: { questions: QuestionInput[]; errors: string[] }) {
    if (result.errors.length) {
      onError(result.errors.slice(0, 5).join('  •  '))
    }
    if (result.questions.length) {
      onAdd(result.questions)
    } else if (!result.errors.length) {
      onError('No questions found in the input.')
    }
  }

  async function handleParseText() {
    if (!text.trim()) return
    setParsing(true)
    try {
      report(await parseText(text, 'auto'))
      setText('')
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e))
    } finally {
      setParsing(false)
    }
  }

  async function handleFile(file: File | undefined) {
    if (!file) return
    setParsing(true)
    try {
      report(await parseFile(file))
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e))
    } finally {
      setParsing(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <Tabs defaultValue="single" className="w-full">
      <TabsList>
        <TabsTrigger value="single">One at a time</TabsTrigger>
        <TabsTrigger value="paste">Bulk paste</TabsTrigger>
        <TabsTrigger value="upload">Upload file</TabsTrigger>
      </TabsList>

      <TabsContent value="single" className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="single-question" className="text-xs text-muted-foreground">
            Question
          </Label>
          <Input
            id="single-question"
            ref={questionRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What is the capital of Japan?"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="single-answer" className="text-xs text-muted-foreground">
            Correct answer
          </Label>
          <Input
            id="single-answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleAddSingle()
              }
            }}
            placeholder="Tokyo"
          />
        </div>
        <Button onClick={handleAddSingle} disabled={!question.trim() || !answer.trim()}>
          Add question
        </Button>
      </TabsContent>

      <TabsContent value="paste" className="space-y-3">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          className="min-h-40 font-mono text-sm"
        />
        <Button onClick={handleParseText} disabled={parsing || !text.trim()}>
          {parsing ? 'Adding…' : 'Add questions'}
        </Button>
      </TabsContent>

      <TabsContent value="upload" className="space-y-3">
        <label
          htmlFor="file-input"
          className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-sm text-muted-foreground cursor-pointer hover:bg-accent/40 transition-colors"
        >
          <Upload className="size-6" />
          <span>Click to choose a CSV, JSON, TSV, or TXT file</span>
        </label>
        <input
          id="file-input"
          ref={fileRef}
          type="file"
          accept=".csv,.json,.tsv,.txt"
          className="sr-only"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </TabsContent>
    </Tabs>
  )
}
