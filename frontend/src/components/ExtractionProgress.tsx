import { Check, Loader2 } from 'lucide-react'
import type { ExtractionStep } from '@/lib/types'

interface Step {
  key: ExtractionStep
  label: string
}

const STEPS: Step[] = [
  { key: 'validating', label: 'Validating URL' },
  { key: 'fetching', label: 'Fetching post' },
  { key: 'reading_media', label: 'Reading media' },
  { key: 'preparing', label: 'Preparing downloads' },
]

interface ExtractionProgressProps {
  currentStep: ExtractionStep
  error: string | null
}

function stepIndex(step: ExtractionStep): number {
  return STEPS.findIndex((s) => s.key === step)
}

export function ExtractionProgress({ currentStep, error }: ExtractionProgressProps) {
  const current = stepIndex(currentStep)

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Extraction progress"
      className="flex flex-col gap-3 w-full max-w-sm mx-auto"
    >
      {STEPS.map((step, i) => {
        const done = current > i || currentStep === 'done'
        const active = current === i
        const pending = current < i

        return (
          <div
            key={step.key}
            className={[
              'flex items-center gap-3 text-sm transition-all duration-300',
              done ? 'text-foreground' : active ? 'text-foreground' : 'text-muted-foreground/50',
            ].join(' ')}
          >
            <span
              className={[
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-200',
                done
                  ? 'border-emerald-500 bg-emerald-500/10'
                  : active
                  ? 'border-white bg-white/10'
                  : 'border-zinc-800 bg-transparent',
              ].join(' ')}
              aria-hidden
            >
              {done ? (
                <Check size={11} className="text-emerald-400" strokeWidth={2.5} />
              ) : active ? (
                <Loader2 size={11} className="text-white animate-spin" />
              ) : null}
            </span>
            <span>{step.label}</span>
            {done && (
              <span className="ml-auto text-xs text-emerald-400" aria-hidden>
                ✓
              </span>
            )}
          </div>
        )
      })}

      {error && (
        <p role="alert" className="mt-2 rounded-lg border border-red-900/50 bg-red-950/50 p-3 text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  )
}
