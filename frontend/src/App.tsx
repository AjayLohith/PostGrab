import { useState, useCallback, useEffect } from 'react'
import { ToastProvider, ToastViewport, Toast, ToastTitle, ToastDescription, ToastClose } from '@/components/ui/toast'
import { UrlInput } from '@/components/UrlInput'
import { ExtractionProgress } from '@/components/ExtractionProgress'
import { ResultPage } from '@/components/ResultPage'
import { api, ApiError } from '@/lib/api'
import { useToast } from '@/hooks/useToast'
import type { ExtractResponse, ExtractionStep } from '@/lib/types'

export default function App() {
  const [page, setPage] = useState<'home' | 'result'>('home')
  const [extractResult, setExtractResult] = useState<ExtractResponse | null>(null)
  const [extractionStep, setExtractionStep] = useState<ExtractionStep>('idle')
  const [extractionError, setExtractionError] = useState<string | null>(null)
  const { toasts, toast, dismiss } = useToast()

  const isExtracting = extractionStep !== 'idle' && extractionStep !== 'done' && extractionStep !== 'error'

  // Handle browser back and forward navigation
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      if (event.state && event.state.page === 'result') {
        setPage('result')
      } else {
        setPage('home')
        setExtractResult(null)
        setExtractionStep('idle')
        setExtractionError(null)
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const handleExtract = useCallback(async (url: string) => {
    setExtractionError(null)
    setExtractionStep('validating')

    // Brief visual pause on each step so progress feels real
    await delay(300)
    setExtractionStep('fetching')

    try {
      // Start the real request
      const extractPromise = api.extract(url)

      // Animate through steps while we wait
      await delay(700)
      setExtractionStep('reading_media')
      await delay(600)
      setExtractionStep('preparing')

      const result = await extractPromise

      setExtractionStep('done')
      await delay(300)
      setExtractResult(result)
      setPage('result')
      setExtractionStep('idle')

      // Push history state so browser Back button returns to the clean URL input
      const postSlug = result.post.author_handle
        ? `${result.post.author_handle}_${result.post.id}`
        : result.job_id
      window.history.pushState({ page: 'result', jobId: result.job_id }, '', `/?post=${postSlug}`)
    } catch (e) {
      setExtractionStep('error')
      const msg =
        e instanceof ApiError
          ? e.message
          : 'Something went wrong. Please try again.'
      setExtractionError(msg)
    }
  }, [])

  const handleBack = useCallback(() => {
    if (window.history.state && window.history.state.page === 'result') {
      window.history.back()
    } else {
      setPage('home')
      setExtractResult(null)
      setExtractionStep('idle')
      setExtractionError(null)
      window.history.pushState(null, '', window.location.pathname)
    }
  }, [])

  const handleError = useCallback(
    (msg: string) => {
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    },
    [toast],
  )

  return (
    <ToastProvider>
      <div className="min-h-dvh flex flex-col bg-[#09090b]">
        {/* ── Navbar ────────────────────────────────────────────────── */}
        <header className="sticky top-0 z-50 backdrop-blur-md bg-[#09090b]/80 border-b border-zinc-800/60">
          <div className="max-w-3xl mx-auto flex items-center justify-between px-4 sm:px-6 h-14 sm:h-16">
            <button
              onClick={handleBack}
              className="flex items-center gap-2.5 group focus-visible:outline-none"
              aria-label="PostGrab home"
            >
              {/* Logo Mark */}
              <div className="relative w-9 h-9 sm:w-10 sm:h-10 flex items-center justify-center" aria-hidden>
                {/* Outer ring */}
                <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 group-hover:from-emerald-500/30 group-hover:to-cyan-500/30 transition-colors" />
                {/* Inner icon surface */}
                <div className="relative w-full h-full rounded-xl bg-zinc-900 border border-zinc-700/60 group-hover:border-zinc-600 flex items-center justify-center transition-colors">
                  <svg viewBox="0 0 24 24" className="w-5 h-5 sm:w-[22px] sm:h-[22px]" fill="none">
                    {/* Download arrow */}
                    <path d="M12 4v12m0 0l-4.5-4.5M12 16l4.5-4.5" stroke="#34d399" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
                    {/* Bottom tray */}
                    <path d="M5 18h14" stroke="#a1a1aa" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </div>
              </div>
              {/* Brand name */}
              <div className="flex flex-col leading-none">
                <span className="font-bold text-[15px] sm:text-base tracking-tight text-zinc-100 group-hover:text-white transition-colors">
                  PostGrab
                </span>
                <span className="text-[10px] sm:text-[11px] text-zinc-500 font-medium tracking-wide">
                  X Post Downloader
                </span>
              </div>
            </button>

            {/* Right side — Status badge */}
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[11px] font-medium text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                HD Ready
              </span>
            </div>
          </div>
          {/* Accent line */}
          <div className="h-[1px] bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent" />
        </header>

        {/* ── Main ──────────────────────────────────────────────────── */}
        <main className="flex-1 flex flex-col px-4 sm:px-6 py-8 sm:py-16">
          <div className="max-w-2xl mx-auto w-full flex-1 flex flex-col">
            {page === 'home' ? (
              <div className="flex flex-col items-center gap-8 sm:gap-10 flex-1">
                {/* Hero */}
                <div className="text-center space-y-3 pt-4 sm:pt-0">
                  <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-zinc-100">
                    Download any X post
                  </h1>
                  <p className="text-zinc-400 text-sm sm:text-base max-w-md mx-auto leading-relaxed">
                    Paste a public post URL and get the tweet image, videos, and photos — all in one place.
                  </p>
                </div>

                {/* URL input */}
                <UrlInput onSubmit={handleExtract} isLoading={isExtracting} />

                {/* Progress */}
                {isExtracting && (
                  <div className="animate-fade-in w-full">
                    <ExtractionProgress
                      currentStep={extractionStep}
                      error={null}
                    />
                  </div>
                )}

                {/* Error */}
                {extractionStep === 'error' && extractionError && (
                  <div className="animate-fade-in w-full max-w-sm mx-auto">
                    <ExtractionProgress
                      currentStep="error"
                      error={extractionError}
                    />
                    <button
                      className="mt-4 mx-auto flex text-sm text-muted-foreground hover:text-foreground transition-colors underline underline-offset-4"
                      onClick={() => {
                        setExtractionStep('idle')
                        setExtractionError(null)
                      }}
                    >
                      Try again
                    </button>
                  </div>
                )}
              </div>
            ) : (
              extractResult && (
                <ResultPage
                  result={extractResult}
                  onBack={handleBack}
                  onError={handleError}
                />
              )
            )}
          </div>
        </main>

        {/* ── Footer ────────────────────────────────────────────────── */}
        <footer className="border-t border-zinc-800/60 px-4 py-4">
          <p className="text-center text-[11px] sm:text-xs text-zinc-600">
            For public posts only · No data stored · Open source
          </p>
        </footer>
      </div>

      {/* Toasts */}
      {toasts.map((t) => (
        <Toast key={t.id} variant={t.variant} open onOpenChange={(open) => !open && dismiss(t.id)}>
          <div className="flex-1 min-w-0">
            <ToastTitle>{t.title}</ToastTitle>
            {t.description && <ToastDescription>{t.description}</ToastDescription>}
          </div>
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  )
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
