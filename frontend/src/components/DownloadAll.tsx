import { Download, Archive, Loader2, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { useDirectDownload } from '@/hooks/useDirectDownload'

interface DownloadAllProps {
  downloadCtrl: ReturnType<typeof useDirectDownload>
}

export function DownloadAll({ downloadCtrl }: DownloadAllProps) {
  const {
    isDownloading,
    isZipDownloading,
    statusText,
    completed,
    handleDirectDownload,
    handleZipDownload,
    isBoth,
    mediaTypeLabel,
    buttonLabel,
  } = downloadCtrl

  return (
    <section aria-labelledby="dl-all-heading" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2
          id="dl-all-heading"
          className="text-[11px] sm:text-xs font-semibold uppercase tracking-widest text-muted-foreground"
        >
          {isBoth ? 'Download Together' : 'Batch Download'}
        </h2>
        <span className="text-[11px] text-emerald-400/90 font-medium">
          No ZIP extraction needed
        </span>
      </div>

      <div className="surface-card rounded-xl p-3 sm:p-4 space-y-3 border border-zinc-800 bg-zinc-900/40">
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          {isBoth
            ? `Download both the tweet image (.png) and the ${mediaTypeLabel.toLowerCase()} (.mp4) directly into your downloads folder with a single click.`
            : `Download the tweet image and all files directly as individual normal files — no extracting archives.`}
        </p>

        {/* Primary Action: Direct Download without ZIP */}
        <Button
          size="lg"
          className="w-full gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-lg shadow-emerald-950/40 transition-all h-11 text-sm sm:text-base"
          onClick={handleDirectDownload}
          disabled={isDownloading || isZipDownloading}
          aria-label={buttonLabel}
          aria-busy={isDownloading}
        >
          {isDownloading ? (
            <>
              <Loader2 size={16} className="animate-spin text-white" aria-hidden />
              <span>{statusText || 'Downloading…'}</span>
            </>
          ) : completed ? (
            <>
              <Check size={16} className="text-white" aria-hidden />
              <span>Downloaded!</span>
            </>
          ) : (
            <>
              <Download size={16} aria-hidden />
              <span>{buttonLabel}</span>
            </>
          )}
        </Button>

        {/* Status indicator when active */}
        {isDownloading && statusText && (
          <p className="text-xs text-center text-emerald-400 font-medium animate-pulse">
            {statusText}
          </p>
        )}

        {/* Secondary option: ZIP Archive */}
        <div className="pt-1 flex items-center justify-center">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 h-8 gap-1.5"
            onClick={handleZipDownload}
            disabled={isDownloading || isZipDownloading}
          >
            {isZipDownloading ? (
              <>
                <Loader2 size={13} className="animate-spin" aria-hidden />
                <span>Building ZIP…</span>
              </>
            ) : (
              <>
                <Archive size={13} aria-hidden />
                <span>Prefer a single archive? Download as .zip</span>
              </>
            )}
          </Button>
        </div>
      </div>
    </section>
  )
}
