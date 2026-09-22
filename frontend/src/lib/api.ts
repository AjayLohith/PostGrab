import type {
  ExtractResponse,
  RenderOptions,
  RenderResponse,
} from './types'

const rawApiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '')
const API_BASE = rawApiUrl ? `${rawApiUrl}/api` : '/api'

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    return res.json() as Promise<T>
  }

  let message = `Request failed (${res.status})`
  let code: string | undefined

  try {
    const body = await res.json()
    // FastAPI can return { detail: "..." } or { error: "...", code: "..." }
    message = body.detail ?? body.error ?? message
    code = body.code
  } catch {
    // ignore parse errors
  }

  throw new ApiError(res.status, message, code)
}

export const api = {
  /** Extract a public X post URL */
  extract(url: string): Promise<ExtractResponse> {
    return fetch(`${API_BASE}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }).then((r) => handleResponse<ExtractResponse>(r))
  },

  /** Render a tweet card PNG */
  render(jobId: string, options: RenderOptions): Promise<RenderResponse> {
    return fetch(`${API_BASE}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, ...options }),
    }).then((r) => handleResponse<RenderResponse>(r))
  },

  /** Get the URL for a specific job asset */
  assetUrl(jobId: string, assetId: string): string {
    return `${API_BASE}/download/${jobId}/${assetId}`
  },

  /** Get the URL for the rendered tweet card preview image */
  tweetCardPreviewUrl(jobId: string): string {
    return `${API_BASE}/download/${jobId}/tweet_card`
  },

  /** Download rendered tweet card image as a Blob */
  async downloadTweetCard(jobId: string): Promise<Blob> {
    const res = await fetch(`${API_BASE}/download/${jobId}/tweet_card`)
    if (!res.ok) {
      await handleResponse(res)
    }
    return res.blob()
  },

  /** Download and cache a media item, returning its file contents */
  async downloadMedia(jobId: string, mediaIndex: number): Promise<Blob> {
    const res = await fetch(`${API_BASE}/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, media_index: mediaIndex }),
    })
    if (!res.ok) {
      await handleResponse(res)
    }
    return res.blob()
  },

  /** Prepare media download on backend and return download URL for direct browser streaming */
  async prepareMediaDownload(
    jobId: string,
    mediaIndex: number,
  ): Promise<{ status: string; asset_id: string; filename: string; download_url: string }> {
    const res = await fetch(`${API_BASE}/download/prepare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, media_index: mediaIndex }),
    })
    if (!res.ok) {
      await handleResponse(res)
    }
    return res.json() as Promise<{ status: string; asset_id: string; filename: string; download_url: string }>
  },

  /** Direct streaming download URL for media */
  getMediaDownloadUrl(jobId: string, mediaIndex: number): string {
    return `${API_BASE}/download/${jobId}/media/${mediaIndex}`
  },

  /** Download all as ZIP — returns a Blob */
  async downloadAll(jobId: string, includeTweetCard = true): Promise<Blob> {
    const res = await fetch(`${API_BASE}/download-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, include_tweet_card: includeTweetCard }),
    })
    if (!res.ok) {
      await handleResponse(res) // will throw
    }
    return res.blob()
  },

  /** Health check */
  health(): Promise<{ status: string }> {
    return fetch(`${API_BASE}/health`).then((r) => handleResponse(r))
  },
}

export { ApiError }
