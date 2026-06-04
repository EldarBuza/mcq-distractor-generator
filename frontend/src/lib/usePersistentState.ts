import { useEffect, useState } from 'react'

/**
 * Like useState, but transparently mirrors the value to localStorage so it
 * survives a page reload. Reads the stored value once on mount; writes on every
 * change. All storage access is guarded — a disabled/full localStorage (or
 * malformed JSON) simply falls back to the in-memory initial value.
 */
export function usePersistentState<T>(
  key: string,
  initial: T,
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw !== null ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // Quota exceeded or storage unavailable — keep working in-memory.
    }
  }, [key, value])

  return [value, setValue]
}
