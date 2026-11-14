import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

interface Result<T> {
  key: string
  data: T | null
  error: string | null
}

/**
 * Minimal data hook for the mock phase (replaced by the generated API client later).
 * `loading` is true whenever the latest result belongs to an older key, so there is no
 * synchronous setState inside the effect. Previous data stays available while reloading.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [tick, setTick] = useState(0)
  const key = `${tick}|${JSON.stringify(deps)}`
  const [res, setRes] = useState<Result<T>>({ key: '', data: null, error: null })
  const fnRef = useRef(fn)

  useEffect(() => {
    fnRef.current = fn
  })

  useEffect(() => {
    let live = true
    fnRef.current().then(
      (data) => live && setRes({ key, data, error: null }),
      (e: unknown) => live && setRes((prev) => ({ key, data: prev.data, error: e instanceof Error ? e.message : 'Something went wrong' })),
    )
    return () => {
      live = false
    }
  }, [key])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data: res.data, loading: res.key !== key, error: res.key === key ? res.error : null, reload }
}
