import { ArrowLeft, Download, Loader2, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { MediaSection } from './MediaSection'
import { TweetCardCustomizer } from './TweetCardCustomizer'
import { DownloadAll } from './DownloadAll'
import { useRender } from '@/hooks/useRender'
import { useDirectDownload } from '@/hooks/useDirectDownload'
import { DEFAULT_RENDER_OPTIONS } from '@/lib/types'
import type { ExtractResponse } from '@/lib/types'

interface ResultPageProps {
  result: ExtractResponse
  onBack: () => void
  onError: (msg: string) => void
}

export function ResultPage({ result, onBack, onError }: ResultPageProps) {
  const { post, job_id: jobId, capabilities } = result

  const {
    options,
    updateOptions,
    previewUrl,
    isRendering,
    renderError,
    renderResult,
  } = useRender(jobId, DEFAULT_RENDER_OPTIONS)

  const hasMedia = capabilities.video || capabilities.gif || capabilities.images

  const downloadCtrl = useDirectDownload({
    jobId,
    post,
    renderFilename: renderResult?.filename ?? 'tweet.png',
    hasTweetCard: Boolean(capabilities.tweet_image),
    onError,
  })

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-slide-up pb-12 sm:pb-16">
      {/* Top Header Bar: Back on left, Quick Download Both/All on right */}
      <div className="flex items-center justify-between gap-3 pt-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={onBack}
          className="gap-1.5 -ml-2 text-zinc-400 hover:text-white text-xs sm:text-sm"
          aria-label="Start a new download"
        >
          <ArrowLeft size={14} aria-hidden />
          New download
        </Button>

        {/* Top-Right Quick Download Both/All Action */}
        {(hasMedia || capabilities.tweet_image) && (
          <Button
            size="sm"
            onClick={downloadCtrl.handleDirectDownload}
            disabled={downloadCtrl.isDownloading || downloadCtrl.isZipDownloading}
            className="gap-1.5 sm:gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs sm:text-sm h-9 px-3 sm:px-4 rounded-lg shadow-md shadow-emerald-950/40 transition-all active:scale-[0.98]"
            title={downloadCtrl.buttonLabel}
          >
            {downloadCtrl.isDownloading ? (
              <>
                <Loader2 size={14} className="animate-spin text-white" aria-hidden />
                <span className="truncate max-w-[130px] sm:max-w-none">
                  {downloadCtrl.statusText || 'Downloading…'}
                </span>
              </>
            ) : downloadCtrl.completed ? (
              <>
                <Check size={14} className="text-white" aria-hidden />
                <span>Downloaded!</span>
              </>
            ) : (
              <>
                <Download size={14} aria-hidden />
                <span className="hidden xs:inline sm:inline">
                  {downloadCtrl.buttonLabel}
                </span>
                <span className="inline xs:hidden sm:hidden">
                  {downloadCtrl.compactLabel}
                </span>
              </>
            )}
          </Button>
        )}
      </div>

      {/* 1. In starting: Tweet Image */}
      <TweetCardCustomizer
        jobId={jobId}
        options={options}
        updateOptions={updateOptions}
        previewUrl={previewUrl}
        isRendering={isRendering}
        renderError={renderError}
        filename={renderResult?.filename ?? 'tweet.png'}
      />

      {/* 2. Below: Video / Media */}
      {hasMedia && (
        <>
          <Separator className="border-zinc-800" />
          <MediaSection post={post} jobId={jobId} />
        </>
      )}

      {/* 3. Below: Download both / all files */}
      {(hasMedia || capabilities.tweet_image) && (
        <>
          <Separator className="border-zinc-800" />
          <DownloadAll downloadCtrl={downloadCtrl} />
        </>
      )}
    </div>
  )
}
