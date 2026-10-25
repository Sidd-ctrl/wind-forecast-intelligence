import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, X } from 'lucide-react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const counter = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const pushToast = useCallback(
    ({ text, tone = 'success', duration = 6000 }) => {
      counter.current += 1
      const id = counter.current
      setToasts((current) => [...current, { id, text, tone }])
      window.setTimeout(() => dismiss(id), duration)
    },
    [dismiss]
  )

  const value = useMemo(() => ({ pushToast }), [pushToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast${toast.tone === 'error' ? ' toast--error' : ''}${toast.tone === 'warn' ? ' toast--warn' : ''}`}>
            <span style={{ color: toast.tone === 'error' ? 'var(--crit)' : 'var(--lime)', marginTop: 1 }}>
              {toast.tone === 'error' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
            </span>
            <p className="toast__text">{toast.text}</p>
            <button
              type="button"
              className="btn btn--ghost btn--icon"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              style={{ height: 20, width: 20, marginLeft: 'auto', flex: 'none' }}
            >
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside ToastProvider')
  return context
}
