import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../lib/api'
import type { RenderOptions, RenderResponse } from '../lib/types'

/**
 * Manages tweet card rendering with debounce.
 * Re-renders whenever options change, after a 600ms debounce.
 */
export function useRender(jobId: string | null, initialOptions: RenderOptions) {
  const [options, setOptions] = useState<RenderOptions>(initialOptions)
  const [renderResult, setRenderResult] = useState<RenderResponse | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isRendering, setIsRendering] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const renderCountRef = useRef(0)
  const activeBlobUrlRef = useRef<string | null>(null)

  const render = useCallback(
    async (opts: RenderOptions) => {
      if (!jobId) return
      const thisRender = ++renderCountRef.current
      setIsRendering(true)
      setRenderError(null)
      try {
        const result = await api.render(jobId, opts)
        if (thisRender !== renderCountRef.current) return

        // Download the complete image asset as a Blob before marking ready
        const blob = await api.downloadTweetCard(jobId)
        if (thisRender !== renderCountRef.current) return

        if (!blob || blob.size === 0) {
          throw new Error('Downloaded image asset is empty')
        }

        const objectUrl = URL.createObjectURL(blob)

        // Revoke previous blob URL to prevent memory leaks
        if (activeBlobUrlRef.current) {
          URL.revokeObjectURL(activeBlobUrlRef.current)
        }
        activeBlobUrlRef.current = objectUrl

        setRenderResult(result)
        setPreviewUrl(objectUrl)
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

  // Cleanup debounce and active blob URL on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (activeBlobUrlRef.current) {
        URL.revokeObjectURL(activeBlobUrlRef.current)
      }
    }
  }, [])

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
