// ── Normalized post data (mirrors backend models) ────────────────────────────

export type MediaType = 'image' | 'video' | 'gif'

export interface MediaVariant {
  url: string
  content_type: string | null
  bitrate: number | null
  width: number | null
  height: number | null
  quality_label: string | null
}

export interface MediaItem {
  type: MediaType
  url: string
  width: number | null
  height: number | null
  duration: number | null
  mime_type: string | null
  thumbnail_url: string | null
  file_size: number | null
  variants: MediaVariant[]
}

export interface QuotedPostData {
  id: string
  url?: string | null
  author_name: string
  author_handle: string
  avatar_url: string | null
  text: string
  created_at: string | null
  media: MediaItem[]
}

export interface PostData {
  id: string
  url: string
  author_name: string
  author_handle: string
  avatar_url: string | null
  text: string
  created_at: string | null
  reply_count: number | null
  repost_count: number | null
  like_count: number | null
  view_count: number | null
  media: MediaItem[]
  quoted_post?: QuotedPostData | null
  source: string | null
}

// ── Capabilities ─────────────────────────────────────────────────────────────

export interface VideoQuality {
  label: string
  url: string
  width: number | null
  height: number | null
  bitrate: number | null
}

export interface Capabilities {
  tweet_image: boolean
  video: boolean
  gif: boolean
  images: boolean
  download_all: boolean
  video_qualities: VideoQuality[]
}

// ── API responses ─────────────────────────────────────────────────────────────

export interface ExtractResponse {
  job_id: string
  post: PostData
  capabilities: Capabilities
}

export interface RenderResponse {
  job_id: string
  asset_id: string
  filename: string
  size: number
}

export interface JobStatus {
  job_id: string
  status: 'created' | 'extracting' | 'extracted' | 'rendering' | 'downloading' | 'complete' | 'failed'
  error: string | null
  assets: Array<{
    id: string
    filename: string
    content_type: string
    size: number
  }>
}

// ── Render options ────────────────────────────────────────────────────────────

export type CardTheme = 'light' | 'dark'
export type CardBackground = 'solid' | 'blur'
export type CardShadow = 'none' | 'soft' | 'medium' | 'strong'
export type CardPadding = 'small' | 'medium' | 'large'
export type CardAspectRatio = 'original' | '1:1' | '4:5' | '16:9' | '9:16'

export interface RenderOptions {
  theme: CardTheme
  background: CardBackground
  background_color: string | null
  background_gradient: string[] | null
  radius: number
  shadow: CardShadow
  padding: CardPadding
  aspect_ratio: CardAspectRatio
}

export const DEFAULT_RENDER_OPTIONS: RenderOptions = {
  theme: 'light',
  background: 'solid',
  background_color: '#ffffff',
  background_gradient: null,
  radius: 16,
  shadow: 'none',
  padding: 'medium',
  aspect_ratio: 'original',
}

// ── App state ─────────────────────────────────────────────────────────────────

export type AppPage = 'home' | 'result'

export type ExtractionStep =
  | 'idle'
  | 'validating'
  | 'fetching'
  | 'reading_media'
  | 'preparing'
  | 'done'
  | 'error'
