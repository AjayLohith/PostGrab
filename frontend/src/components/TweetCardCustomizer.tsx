import { useState } from 'react'
import { RefreshCw, Download, Image as ImageIcon, Copy, Check, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { downloadUrl } from '@/lib/utils'
import type {
  RenderOptions,
  CardTheme,
  CardBackground,
  CardShadow,
  CardPadding,
  CardAspectRatio,
} from '@/lib/types'

interface TweetCardCustomizerProps {
  jobId: string
  options: RenderOptions
  updateOptions: (updates: Partial<RenderOptions>) => void
  previewUrl: string | null
  isRendering: boolean
  renderError: string | null
  filename: string
}

const THEMES: { value: CardTheme; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

const BACKGROUNDS: { value: CardBackground; label: string }[] = [
  { value: 'solid', label: 'Solid color' },
  { value: 'blur', label: 'Blurred media' },
]

const SHADOWS: { value: CardShadow; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'soft', label: 'Soft' },
  { value: 'medium', label: 'Medium' },
  { value: 'strong', label: 'Strong' },
]

const PADDINGS: { value: CardPadding; label: string }[] = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
]

const ASPECT_RATIOS: { value: CardAspectRatio; label: string }[] = [
  { value: 'original', label: 'Auto Height (Original Ratio)' },
  { value: '4:5', label: 'Instagram Feed (4:5)' },
  { value: '1:1', label: 'Instagram Square (1:1)' },
  { value: '16:9', label: 'Landscape (16:9)' },
  { value: '9:16', label: 'Story / Reel (9:16)' },
]

// Minimal solid swatches - absolutely zero gradients
const SOLID_SWATCHES = [
  { label: 'White', color: '#ffffff' },
  { label: 'Off-white', color: '#f4f4f5' },
  { label: 'Slate', color: '#1e293b' },
  { label: 'Zinc', color: '#18181b' },
  { label: 'Charcoal', color: '#121214' },
  { label: 'Black', color: '#000000' },
]

export function TweetCardCustomizer({
  options,
  updateOptions,
  previewUrl,
  isRendering,
  renderError,
  filename,
}: TweetCardCustomizerProps) {
  const [copied, setCopied] = useState(false)
  const [isCopying, setIsCopying] = useState(false)

  const handleCopyImage = async () => {
    if (!previewUrl) return
    setIsCopying(true)
    try {
      const resp = await fetch(previewUrl)
      const blob = await resp.blob()
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob }),
      ])
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch (err) {
      console.error('Failed to copy image to clipboard:', err)
    } finally {
      setIsCopying(false)
    }
  }

  return (
    <section aria-labelledby="card-heading" className="space-y-4">
      {/* 2-Column Studio Layout: Left Preview & Actions, Right Scrollable Vertical Card */}
      <div className="flex flex-col md:flex-row gap-5 lg:gap-6 items-start">
        {/* Left Column: Preview + Actions directly underneath */}
        <div className="flex-1 w-full space-y-3 sm:space-y-4">
          <div className="flex items-center justify-between">
            <h2 id="card-heading" className="text-[11px] sm:text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Tweet Image
            </h2>
            {isRendering && (
              <span className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
                <RefreshCw size={12} className="animate-spin" />
                Updating…
              </span>
            )}
          </div>

          {/* Preview Canvas */}
          <div
            className="relative rounded-xl overflow-hidden surface-card flex items-center justify-center p-1.5 sm:p-2.5 border border-zinc-800/80 bg-zinc-900/30"
            style={{ minHeight: 220 }}
            aria-label="Tweet card preview"
            aria-live="polite"
          >
            {previewUrl ? (
              <img
                key={previewUrl}
                src={previewUrl}
                alt="Tweet card preview"
                className="w-full rounded-lg shadow-sm"
                style={{ display: 'block' }}
              />
            ) : (
              <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
                <ImageIcon size={28} className="text-zinc-600" aria-hidden />
                <span className="text-xs sm:text-sm text-zinc-400">Rendering preview…</span>
              </div>
            )}

            {isRendering && (
              <div
                className="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm rounded-xl transition-all"
                aria-hidden
              >
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900/90 border border-zinc-700 text-xs text-white shadow-lg">
                  <RefreshCw size={14} className="animate-spin text-emerald-400" />
                  <span>Updating image…</span>
                </div>
              </div>
            )}
          </div>

          {renderError && (
            <p role="alert" className="text-xs text-red-400 rounded-lg border border-red-900/50 bg-red-950/50 p-2.5">
              {renderError}
            </p>
          )}

          {/* Action buttons: Copy & Download right under the tweet image */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
            <Button
              size="lg"
              variant="outline"
              className="w-full gap-2 border-zinc-800 bg-zinc-900/70 hover:bg-zinc-800 text-zinc-100 hover:text-white font-medium transition-colors h-10 sm:h-11 text-xs sm:text-sm shadow-sm"
              disabled={!previewUrl || isRendering || isCopying}
              onClick={handleCopyImage}
              aria-label="Copy tweet image to clipboard"
            >
              {copied ? (
                <>
                  <Check size={15} className="text-emerald-400" aria-hidden />
                  <span className="text-emerald-400 font-medium">Copied!</span>
                </>
              ) : isCopying ? (
                <>
                  <RefreshCw size={15} className="animate-spin text-zinc-400" aria-hidden />
                  <span>Copying…</span>
                </>
              ) : (
                <>
                  <Copy size={15} className="text-zinc-400" aria-hidden />
                  <span>Copy to Clipboard</span>
                </>
              )}
            </Button>

            <Button
              size="lg"
              className="w-full gap-2 bg-white text-black hover:bg-zinc-200 font-medium transition-colors h-10 sm:h-11 text-xs sm:text-sm shadow-sm"
              disabled={!previewUrl || isRendering}
              onClick={() => {
                if (previewUrl) downloadUrl(previewUrl, filename)
              }}
              aria-label="Download tweet image as PNG"
            >
              <Download size={15} aria-hidden />
              Download Tweet Image
            </Button>
          </div>
        </div>

        {/* Right Column: Scrollable Vertical Customization Card */}
        <div className="w-full md:w-[320px] lg:w-[340px] shrink-0">
          <div className="surface-card rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 space-y-4 shadow-sm md:sticky md:top-20">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800/80">
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={14} className="text-emerald-400" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-200">
                  Customization
                </h3>
              </div>
              <span className="text-[10px] text-zinc-500 font-mono px-2 py-0.5 rounded bg-zinc-800/60 border border-zinc-700/50">
                {options.aspect_ratio === 'original' ? 'Auto Ratio' : options.aspect_ratio}
              </span>
            </div>

            {/* Scrollable controls list */}
            <div className="space-y-4 max-h-[460px] overflow-y-auto pr-1">
              {/* Theme & Background */}
              <div className="grid grid-cols-2 gap-2.5">
                <ControlGroup label="Theme">
                  <Select
                    value={options.theme}
                    onValueChange={(v) => {
                      const newTheme = v as CardTheme
                      updateOptions({
                        theme: newTheme,
                        background_color: newTheme === 'light' ? '#ffffff' : '#000000',
                      })
                    }}
                  >
                    <SelectTrigger aria-label="Card theme" className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {THEMES.map((t) => (
                        <SelectItem key={t.value} value={t.value} className="text-xs">
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </ControlGroup>

                <ControlGroup label="Background">
                  <Select
                    value={options.background}
                    onValueChange={(v) => updateOptions({ background: v as CardBackground })}
                  >
                    <SelectTrigger aria-label="Background type" className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {BACKGROUNDS.map((b) => (
                        <SelectItem key={b.value} value={b.value} className="text-xs">
                          {b.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </ControlGroup>
              </div>

              {/* Shadow & Padding */}
              <div className="grid grid-cols-2 gap-2.5">
                <ControlGroup label="Shadow">
                  <Select
                    value={options.shadow}
                    onValueChange={(v) => updateOptions({ shadow: v as CardShadow })}
                  >
                    <SelectTrigger aria-label="Shadow" className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SHADOWS.map((s) => (
                        <SelectItem key={s.value} value={s.value} className="text-xs">
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </ControlGroup>

                <ControlGroup label="Padding">
                  <Select
                    value={options.padding}
                    onValueChange={(v) => updateOptions({ padding: v as CardPadding })}
                  >
                    <SelectTrigger aria-label="Padding" className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PADDINGS.map((p) => (
                        <SelectItem key={p.value} value={p.value} className="text-xs">
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </ControlGroup>
              </div>

              {/* Aspect ratio */}
              <ControlGroup label="Aspect ratio">
                <Select
                  value={options.aspect_ratio}
                  onValueChange={(v) => updateOptions({ aspect_ratio: v as CardAspectRatio })}
                >
                  <SelectTrigger aria-label="Aspect ratio" className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ASPECT_RATIOS.map((r) => (
                      <SelectItem key={r.value} value={r.value} className="text-xs">
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </ControlGroup>

              {/* Corner radius */}
              <ControlGroup label={`Corner radius — ${options.radius}px`}>
                <Slider
                  min={0}
                  max={32}
                  step={4}
                  value={[options.radius]}
                  onValueChange={([v]) => updateOptions({ radius: v })}
                  aria-label="Corner radius"
                  aria-valuemin={0}
                  aria-valuemax={32}
                  aria-valuenow={options.radius}
                />
                <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                  <span>Square</span>
                  <span>Rounded</span>
                </div>
              </ControlGroup>

              {/* Solid background color selection */}
              {options.background === 'solid' && (
                <ControlGroup label="Background Color">
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-1.5">
                      {SOLID_SWATCHES.map((swatch) => {
                        const isSelected = (options.background_color ?? '#000000').toLowerCase() === swatch.color.toLowerCase()
                        return (
                          <button
                            key={swatch.color}
                            type="button"
                            onClick={() => updateOptions({ background_color: swatch.color })}
                            className={[
                              'flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium border transition-colors',
                              isSelected
                                ? 'border-emerald-400 text-white bg-emerald-500/10'
                                : 'border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200 bg-zinc-900/50',
                            ].join(' ')}
                            title={swatch.label}
                          >
                            <span
                              className="w-2.5 h-2.5 rounded-full border border-zinc-700 shrink-0"
                              style={{ backgroundColor: swatch.color }}
                            />
                            <span className="truncate">{swatch.label}</span>
                          </button>
                        )
                      })}
                    </div>

                    <div className="flex items-center gap-2.5 pt-1">
                      <input
                        type="color"
                        value={options.background_color ?? '#000000'}
                        onChange={(e) => updateOptions({ background_color: e.target.value })}
                        className="h-7 w-10 rounded cursor-pointer border border-zinc-800 bg-transparent p-0.5"
                        aria-label="Pick custom background color"
                      />
                      <span className="text-[11px] text-zinc-400 font-mono">
                        {(options.background_color ?? '#000000').toUpperCase()}
                      </span>
                    </div>
                  </div>
                </ControlGroup>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function ControlGroup({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={['space-y-1.5', className].filter(Boolean).join(' ')}>
      <Label className="text-[11px] text-zinc-400">{label}</Label>
      {children}
    </div>
  )
}
