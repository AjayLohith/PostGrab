import { useState } from 'react'
import { MessageCircle, Repeat2, Heart, BarChart2, ExternalLink } from 'lucide-react'
import { formatCount, formatDate } from '@/lib/utils'
import type { PostData } from '@/lib/types'

interface PostCardProps {
  post: PostData
}

export function PostCard({ post }: PostCardProps) {
  const [avatarError, setAvatarError] = useState(false)
  const initial = (post.author_name || post.author_handle || '?')[0].toUpperCase()
  const avatarSrc = post.avatar_url || (post.author_handle ? `https://unavatar.io/x/${post.author_handle}` : null)

  return (
    <article className="surface-card rounded-xl p-5 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-3">
        {avatarSrc && !avatarError ? (
          <img
            src={avatarSrc}
            alt={`${post.author_name} avatar`}
            className="w-11 h-11 rounded-full shrink-0 object-cover border border-zinc-800"
            onError={() => setAvatarError(true)}
            loading="lazy"
          />
        ) : (
          <div
            className="w-11 h-11 rounded-full shrink-0 bg-zinc-800 border border-zinc-700 flex items-center justify-center text-sm font-semibold text-zinc-300"
            aria-hidden
          >
            {initial}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm truncate">{post.author_name || post.author_handle}</span>
            <span className="text-muted-foreground text-sm truncate">@{post.author_handle}</span>
          </div>
          {post.created_at && (
            <time
              dateTime={post.created_at}
              className="text-xs text-muted-foreground"
            >
              {formatDate(post.created_at)}
            </time>
          )}
        </div>
        <a
          href={post.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View original post on X"
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors p-1 rounded"
        >
          <ExternalLink size={15} aria-hidden />
        </a>
      </div>

      {/* Text */}
      {post.text && (
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground/90">
          {post.text}
        </p>
      )}

      {/* Metrics */}
      {(post.reply_count != null ||
        post.repost_count != null ||
        post.like_count != null ||
        post.view_count != null) && (
        <div className="flex items-center gap-4 pt-1 border-t border-white/5">
          {post.reply_count != null && (
            <MetricItem icon={<MessageCircle size={14} aria-hidden />} value={formatCount(post.reply_count)} label="replies" />
          )}
          {post.repost_count != null && (
            <MetricItem icon={<Repeat2 size={14} aria-hidden />} value={formatCount(post.repost_count)} label="reposts" />
          )}
          {post.like_count != null && (
            <MetricItem icon={<Heart size={14} aria-hidden />} value={formatCount(post.like_count)} label="likes" />
          )}
          {post.view_count != null && (
            <MetricItem icon={<BarChart2 size={14} aria-hidden />} value={formatCount(post.view_count)} label="views" />
          )}
        </div>
      )}
    </article>
  )
}

function MetricItem({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode
  value: string
  label: string
}) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground" aria-label={`${value} ${label}`}>
      {icon}
      <span>{value}</span>
    </span>
  )
}
