import { useEffect, useState } from 'react'
import { getHealth } from '@/lib/api'
import type { HealthResponse } from '@/types'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

type Status = 'loading' | 'ok' | 'error'

function App() {
  const [status, setStatus] = useState<Status>('loading')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string>('')

  // No synchronous setState here — state only changes after the await resolves.
  async function runCheck() {
    try {
      const h = await getHealth()
      setHealth(h)
      setStatus('ok')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('error')
    }
  }

  function check() {
    setStatus('loading')
    setError('')
    void runCheck()
  }

  useEffect(() => {
    // Data fetch on mount: state is set only after the request resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void runCheck()
  }, [])

  return (
    <main className="min-h-svh flex items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>MCQ Distractor Generator</CardTitle>
          <CardDescription>Frontend ↔ backend connectivity check</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status === 'loading' && (
            <p className="text-sm text-muted-foreground">Checking backend…</p>
          )}

          {status === 'ok' && health && (
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span>Backend</span>
                <Badge>online</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>Model</span>
                <code className="text-xs">{health.model}</code>
              </div>
              <div className="flex items-center justify-between">
                <span>API key configured</span>
                <Badge variant={health.api_key_configured ? 'default' : 'destructive'}>
                  {health.api_key_configured ? 'yes' : 'no'}
                </Badge>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="space-y-1 text-sm">
              <Badge variant="destructive">offline</Badge>
              <p className="text-muted-foreground">
                Could not reach the backend. Is it running on port 8000?
              </p>
              <p className="text-xs text-destructive">{error}</p>
            </div>
          )}

          <Button onClick={check} variant="outline" className="w-full">
            Re-check
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}

export default App
