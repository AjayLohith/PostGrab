import { useState, useRef, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowRight, Link2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { isValidXUrl } from '@/lib/utils'

interface UrlInputProps {
  onSubmit: (url: string) => void
  isLoading: boolean
}

export function UrlInput({ onSubmit, isLoading }: UrlInputProps) {
  const [value, setValue] = useState('')
  const [touched, setTouched] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const isValid = isValidXUrl(value)
  const showError = touched && value.length > 0 && !isValid

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!isValid || isLoading) return
    onSubmit(value.trim())
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSubmit(e as unknown as FormEvent)
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text').trim()
    if (isValidXUrl(pasted)) {
      e.preventDefault()
      setValue(pasted)
      setTouched(false)
      // Auto-submit on paste if valid
      setTimeout(() => onSubmit(pasted), 50)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto px-0 sm:px-0">
      <div
        className={[
          'flex items-center gap-2 sm:gap-3 rounded-xl border px-3 sm:px-4 py-2.5 sm:py-3 transition-all duration-150',
          showError
            ? 'border-red-500/60 bg-red-950/20'
            : isValid
            ? 'border-zinc-500 bg-zinc-900/70'
            : 'border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 focus-within:border-zinc-400',
        ].join(' ')}
      >
        <Link2 className="shrink-0 text-zinc-400" size={16} aria-hidden />
        <input
          ref={inputRef}
          type="url"
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setTouched(false)
          }}
          onBlur={() => setTouched(true)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="https://x.com/user/status/..."
          aria-label="X post URL"
          aria-describedby={showError ? 'url-error' : undefined}
          autoComplete="url"
          spellCheck={false}
          className="flex-1 bg-transparent text-sm sm:text-base text-zinc-100 placeholder:text-zinc-500 outline-none min-w-0"
          disabled={isLoading}
        />
        <Button
          type="submit"
          size="sm"
          disabled={!isValid || isLoading}
          className="shrink-0 gap-1.5 bg-white text-black hover:bg-zinc-200 font-medium transition-colors text-xs sm:text-sm h-8 sm:h-9 px-3 sm:px-4"
          aria-label="Fetch post"
        >
          {isLoading ? (
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-3 sm:h-3.5 sm:w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent" aria-hidden />
              <span className="hidden sm:inline">Fetching</span>
              <span className="sm:hidden">...</span>
            </span>
          ) : (
            <span className="flex items-center gap-1">
              Fetch <ArrowRight size={13} aria-hidden />
            </span>
          )}
        </Button>
      </div>

      {showError && (
        <p id="url-error" role="alert" className="mt-2 text-xs sm:text-sm text-red-400 px-1">
          Enter a valid X post URL — e.g. https://x.com/user/status/12345
        </p>
      )}

      <p className="mt-3 text-center text-[11px] sm:text-xs text-muted-foreground">
        Paste any public X post URL. No login required.
      </p>
    </form>
  )
}
