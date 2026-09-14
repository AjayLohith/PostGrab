import { Download, Play, Image as ImageIcon, Video } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { triggerDownload } from '@/lib/utils'
import { api } from '@/lib/api'
import type { PostData, MediaItem } from '@/lib/types'

interface MediaSectionProps {
  post: PostData
  jobId: string
}

export function MediaSection({ post, jobId }: MediaSectionProps) {
  const rootVideos = post.media.filter((m) => m.type === 'video')
  const rootGifs = post.media.filter((m) => m.type === 'gif')
  const rootImages = post.media.filter((m) => m.type === 'image')

  const qMedia = post.quoted_post?.media || []
  const quotedVideos = qMedia.filter((m) => m.type === 'video')
  const quotedGifs = qMedia.filter((m) => m.type === 'gif')
  const quotedImages = qMedia.filter((m) => m.type === 'image')

  // Global flat list matching backend post.all_media_items ordering:
  const allMediaFlat = [
    ...rootVideos,
    ...rootGifs,
    ...rootImages,
    ...quotedVideos,
    ...quotedGifs,
    ...quotedImages,
  ]

  if (allMediaFlat.length === 0) return null

  return (
    <section aria-labelledby="media-heading" className="space-y-4">
      <h2 id="media-heading" className="text-[11px] sm:text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Media Downloads
      </h2>

      {/* Root Videos */}
      {rootVideos.map((item, i) => (
        <VideoItem
          key={`video-${i}`}
          item={item}
          globalIndex={allMediaFlat.indexOf(item)}
          jobId={jobId}
          label={rootVideos.length > 1 ? `Video ${i + 1}` : 'Video'}
        />
      ))}

      {/* Quoted Videos */}
      {quotedVideos.map((item, i) => (
        <VideoItem
          key={`quoted-video-${i}`}
          item={item}
          globalIndex={allMediaFlat.indexOf(item)}
          jobId={jobId}
          label={quotedVideos.length > 1 ? `Quoted Video ${i + 1}` : 'Quoted Video'}
        />
      ))}

      {/* Root GIFs */}
      {rootGifs.map((item, i) => (
        <VideoItem
          key={`gif-${i}`}
          item={item}
          globalIndex={allMediaFlat.indexOf(item)}
          jobId={jobId}
          label={rootGifs.length > 1 ? `GIF ${i + 1}` : 'GIF'}
        />
      ))}

      {/* Quoted GIFs */}
      {quotedGifs.map((item, i) => (
        <VideoItem
          key={`quoted-gif-${i}`}
          item={item}
          globalIndex={allMediaFlat.indexOf(item)}
          jobId={jobId}
          label={quotedGifs.length > 1 ? `Quoted GIF ${i + 1}` : 'Quoted GIF'}
        />
      ))}

      {/* Root Images */}
      {rootImages.length > 0 && (
        <div className="space-y-3">
          <div
            className={[
              'grid gap-2 rounded-xl overflow-hidden',
              rootImages.length === 1 ? 'grid-cols-1' : 'grid-cols-2',
            ].join(' ')}
          >
            {rootImages.map((item, i) => (
              <ImageItem key={`img-${i}`} item={item} index={i} />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {rootImages.map((item, i) => (
              <Button
                key={`dl-img-${i}`}
                size="sm"
                variant="outline"
                className="gap-1.5 border-zinc-800 hover:bg-zinc-800 hover:text-white text-xs sm:text-sm flex-1 sm:flex-none"
                onClick={() => {
                  const idx = allMediaFlat.indexOf(item)
                  void api.downloadMedia(jobId, idx).then((blob) => {
                    triggerDownload(blob, `image_${i + 1}.jpg`)
                  })
                }}
                aria-label={`Download image ${i + 1}`}
              >
                <Download size={13} aria-hidden />
                {rootImages.length > 1 ? `Image ${i + 1}` : 'Download Image'}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Quoted Images */}
      {quotedImages.length > 0 && (
        <div className="space-y-3">
          <div
            className={[
              'grid gap-2 rounded-xl overflow-hidden',
              quotedImages.length === 1 ? 'grid-cols-1' : 'grid-cols-2',
            ].join(' ')}
          >
            {quotedImages.map((item, i) => (
              <ImageItem key={`quoted-img-${i}`} item={item} index={i} />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {quotedImages.map((item, i) => (
              <Button
                key={`dl-quoted-img-${i}`}
                size="sm"
                variant="outline"
                className="gap-1.5 border-zinc-800 hover:bg-zinc-800 hover:text-white text-xs sm:text-sm flex-1 sm:flex-none"
                onClick={() => {
                  const idx = allMediaFlat.indexOf(item)
                  void api.downloadMedia(jobId, idx).then((blob) => {
                    triggerDownload(blob, `quoted_image_${i + 1}.jpg`)
                  })
                }}
                aria-label={`Download quoted image ${i + 1}`}
              >
                <Download size={13} aria-hidden />
                {quotedImages.length > 1 ? `Quoted Image ${i + 1}` : 'Download Quoted Image'}
              </Button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function VideoItem({
  item,
  globalIndex,
  jobId,
  label,
}: {
  item: MediaItem
  globalIndex: number
  jobId: string
  label: string
}) {
  return (
    <div className="space-y-3">
      {/* Thumbnail */}
      <div className="relative rounded-xl overflow-hidden bg-zinc-900 border border-zinc-800 aspect-video">
        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={`${label} thumbnail`}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Video size={28} className="text-zinc-600" aria-hidden />
          </div>
        )}
        {/* Play overlay */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          aria-hidden
        >
          <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center border border-zinc-700">
            <Play size={16} className="text-white fill-white ml-0.5 sm:w-[18px] sm:h-[18px]" />
          </div>
        </div>
        {/* Duration */}
        {item.duration && (
          <div className="absolute bottom-2 right-2 rounded bg-black/80 px-1.5 py-0.5 text-[10px] sm:text-xs text-white tabular-nums border border-zinc-800">
            {formatDuration(item.duration)}
          </div>
        )}
        {item.type === 'gif' && (
          <div className="absolute top-2 left-2 rounded bg-black/80 px-1.5 py-0.5 text-[10px] sm:text-xs text-white font-medium border border-zinc-800">
            GIF
          </div>
        )}
      </div>

      {/* Download button */}
      <Button
        size="sm"
        variant="outline"
        className="gap-1.5 w-full border-zinc-800 hover:bg-zinc-800 hover:text-white text-xs sm:text-sm"
        onClick={() => {
          void api.downloadMedia(jobId, globalIndex).then((blob) => {
            triggerDownload(blob, `${label.toLowerCase().replace(' ', '_')}.mp4`)
          })
        }}
        aria-label={`Download ${label}`}
      >
        <Download size={13} aria-hidden />
        Download {label}
        {item.width && item.height && (
          <span className="ml-1 text-[10px] sm:text-xs text-zinc-500">
            {item.width}×{item.height}
          </span>
        )}
      </Button>
    </div>
  )
}

function ImageItem({ item, index }: { item: MediaItem; index: number }) {
  return (
    <div className="relative bg-zinc-900 border border-zinc-800 overflow-hidden aspect-square">
      {item.url ? (
        <img
          src={item.url}
          alt={`Image ${index + 1}`}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <ImageIcon size={20} className="text-zinc-600" aria-hidden />
        </div>
      )}
    </div>
  )
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
