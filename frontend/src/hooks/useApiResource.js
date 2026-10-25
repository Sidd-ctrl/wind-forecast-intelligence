import { useCallback, useEffect, useRef, useState } from 'react'

export function useApiResource(loader, deps = []) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    setState((previous) => ({
      status: previous.data ? 'refreshing' : 'loading',
      data: previous.data,
      error: null
    }))

    loaderRef
      .current({ signal: controller.signal })
      .then((data) => {
        if (!active) return
        setState({ status: 'ready', data, error: null })
      })
      .catch((error) => {
        if (!active || error.name === 'AbortError') return
        setState({ status: 'error', data: null, error })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [...deps, attempt])

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  return { ...state, retry, isLoading: state.status === 'loading', isRefreshing: state.status === 'refreshing' }
}
