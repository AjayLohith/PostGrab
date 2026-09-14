import { useState, useCallback } from 'react'
import { api } from '../lib/api'
import { triggerDownload, sleep } from '../lib/utils'
import type { PostData, MediaItem } from '../lib/types'

interface UseDirectDownloadOptions {
  jobId: string
  post: PostData
  renderFilename?: string
  hasTweetCard?: boolean
  onError: (msg: string) => void
}

export function useDirectDownload({
  jobId,
  post,
  renderFilename = 'tweet.png',
  hasTweetCard = true,
  onError,
}: UseDirectDownloadOptions) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [isZipDownloading, setIsZipDownloading] = useState(false)
  const [statusText, setStatusText] = useState<string | null>(null)
  const [completed, setCompleted] = useState(false)

  const rootVideos = post.media.filter((m: MediaItem) => m.type === 'video')
  const rootGifs = post.media.filter((m: MediaItem) => m.type === 'gif')
  const rootImages = post.media.filter((m: MediaItem) => m.type === 'image')

  const qMedia = post.quoted_post?.media || []
  const quotedVideos = qMedia.filter((m: MediaItem) => m.type === 'video')
  const quotedGifs = qMedia.filter((m: MediaItem) => m.type === 'gif')
  const quotedImages = qMedia.filter((m: MediaItem) => m.type === 'image')

  const allMedia = [
    ...rootVideos,
    ...rootGifs,
    ...rootImages,
    ...quotedVideos,
    ...quotedGifs,
    ...quotedImages,
  ]

  const totalFiles = (hasTweetCard ? 1 : 0) + allMedia.length
  const isBoth = hasTweetCard && allMedia.length === 1
  const mediaTypeLabel = allMedia.length > 0
    ? allMedia[0].type === 'video'
      ? 'Video'
      : allMedia[0].type === 'gif'
        ? 'GIF'
        : 'Photo'
    : 'Media'

  const buttonLabel = isBoth
    ? `Download Both (Image + ${mediaTypeLabel})`
    : allMedia.length > 1
      ? `Download All (${totalFiles} Files)`
      : hasTweetCard
        ? 'Download Tweet Image'
        : 'Download Media'

  const compactLabel = isBoth
    ? `Download Both`
    : allMedia.length > 1
      ? `Download All (${totalFiles})`
      : 'Download Image'

  const handleDirectDownload = useCallback(async () => {
    if (isDownloading || isZipDownloading) return
    setIsDownloading(true)
    setCompleted(false)
    setStatusText('Preparing files…')

    const handle = (post.author_handle || 'post').replace(/[^a-zA-Z0-9_]/g, '')
    const id = (post.id || 'unknown').replace(/[^a-zA-Z0-9_]/g, '')

    try {
      let count = 0

      // 1. Download Tweet Image
      if (hasTweetCard) {
        count++
        setStatusText(`Downloading tweet image (${count}/${totalFiles})…`)
        const tweetBlob = await api.downloadTweetCard(jobId)
        triggerDownload(tweetBlob, renderFilename || `${handle}_${id}_tweet.png`)
        if (allMedia.length > 0) {
          await sleep(400)
        }
      }

      // 2. Download all media items
      for (let i = 0; i < allMedia.length; i++) {
        count++
        const item = allMedia[i]
        const ext = item.type === 'image' ? 'jpg' : 'mp4'
        const label = item.type === 'video' ? 'video' : item.type === 'gif' ? 'gif' : 'image'
        setStatusText(`Downloading ${label} (${count}/${totalFiles})…`)

        const mediaBlob = await api.downloadMedia(jobId, i)
        const filename = `${handle}_${id}_${label}_${i + 1}.${ext}`
        triggerDownload(mediaBlob, filename)

        if (i < allMedia.length - 1) {
          await sleep(400)
        }
      }

      setCompleted(true)
      setStatusText('Downloaded!')
      setTimeout(() => {
        setCompleted(false)
        setStatusText(null)
      }, 3500)
    } catch (e) {
      onError(
        e instanceof Error
          ? e.message
          : 'Could not download one or more files. Please try again.',
      )
      setStatusText(null)
    } finally {
      setIsDownloading(false)
    }
  }, [isDownloading, isZipDownloading, hasTweetCard, totalFiles, allMedia, jobId, renderFilename, post, onError])

  const handleZipDownload = useCallback(async () => {
    if (isDownloading || isZipDownloading) return
    setIsZipDownloading(true)
    const handle = (post.author_handle || 'post').replace(/[^a-zA-Z0-9_]/g, '')
    const id = (post.id || 'unknown').replace(/[^a-zA-Z0-9_]/g, '')

    try {
      const blob = await api.downloadAll(jobId, hasTweetCard)
      triggerDownload(blob, `${handle}_${id}.zip`)
    } catch (e) {
      onError(
        e instanceof Error
          ? e.message
          : 'Could not build the ZIP archive. Please try again.',
      )
    } finally {
      setIsZipDownloading(false)
    }
  }, [isDownloading, isZipDownloading, jobId, hasTweetCard, post, onError])

  return {
    isDownloading,
    isZipDownloading,
    statusText,
    completed,
    handleDirectDownload,
    handleZipDownload,
    totalFiles,
    isBoth,
    mediaTypeLabel,
    buttonLabel,
    compactLabel,
    hasMedia: allMedia.length > 0,
  }
}
