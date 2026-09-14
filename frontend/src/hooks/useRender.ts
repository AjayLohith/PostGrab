import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '@/lib/api'
import type { RenderOptions, RenderResponse } from '@/lib/types'

/**
 * Manages tweet card rendering with debounce.
 * Re-renders whenever options change, after a 600ms debounce.
 */
export function useRender(jobId: string | null, initialOptions: RenderOptions) {
  const [options, setOptions] = useState<RenderOptions>(initialOptions)
  const [renderResult, setRenderResult] = useState<RenderResponse | null>(null)
  const [isRendering, setIsRendering] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const renderCountRef = useRef(0)

  const render = useCallback(
    async (opts: RenderOptions) => {
      if (!jobId) return
      const thisRender = ++renderCountRef.current
      setIsRendering(true)
      setRenderError(null)
      try {
        const result = await api.render(jobId, opts)
        // Only update if this is still the latest render
        if (thisRender === renderCountRef.current) {
          setRenderResult(result)
        }
      } catch (e) {
        if (thisRender === renderCountRef.current) {
          setRenderError(e instanceof Error ? e.message : 'Render failed')
        }
      } finally {
        if (thisRender === renderCountRef.current) {
          setIsRendering(false)
        }
      }
    },
    [jobId],
  )

  // Initial render
  useEffect(() => {
    if (jobId) {
      render(options)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  // Debounced re-render on options change
  const updateOptions = useCallback(
    (updates: Partial<RenderOptions>) => {
      const newOpts = { ...options, ...updates }
      setOptions(newOpts)

      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        render(newOpts)
      }, 600)
    },
    [options, render],
  )

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  // Preview URL — add cache-bust so img element reloads
  const previewUrl = jobId && renderResult
    ? `${api.tweetCardPreviewUrl(jobId)}?v=${renderResult.size}`
    : null

  return {
    options,
    updateOptions,
    renderResult,
    isRendering,
    renderError,
    previewUrl,
    rerender: () => render(options),
  }
}
