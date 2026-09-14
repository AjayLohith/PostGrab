import { useState, useCallback } from 'react'

export interface ToastItem {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'destructive'
}

let idCounter = 0

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const toast = useCallback(
    (opts: Omit<ToastItem, 'id'>) => {
      const id = `toast-${++idCounter}`
      setToasts((prev) => [...prev, { ...opts, id }])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 4000)
    },
    [],
  )

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return { toasts, toast, dismiss }
}
