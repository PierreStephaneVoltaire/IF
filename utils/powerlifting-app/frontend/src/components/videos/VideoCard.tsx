import { Play } from 'lucide-react'
import type { VideoLibraryItem } from '@powerlifting/types'
import { formatFileSize } from '@/utils/s3'

interface VideoCardProps {
  item: VideoLibraryItem
  onClick: () => void
}

export default function VideoCard({ item, onClick }: VideoCardProps) {
  const { video, session_date, day, week_number, phase_name } = item
  const hasThumbnail = video.thumbnail_url && video.thumbnail_status === 'ready'

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-card border border-border rounded-lg overflow-hidden hover:border-primary/50 transition-colors group"
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-secondary flex items-center justify-center">
        {hasThumbnail ? (
          <img
            src={video.thumbnail_url}
            alt={video.exercise_name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center gap-1 text-muted-foreground">
            <Play className="w-8 h-8" />
            <span className="text-xs">Processing...</span>
          </div>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
          <Play className="w-10 h-10 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>

      {/* Info */}
      <div className="p-3 space-y-1">
        <p className="font-semibold text-sm">{video.exercise_name}</p>
        <p className="text-xs text-muted-foreground">
          {session_date} · {day} · W{week_number} · {phase_name}
        </p>
        {video.set_number && (
          <p className="text-xs text-muted-foreground">Set {video.set_number}</p>
        )}
        {video.notes && (
          <p className="text-xs text-muted-foreground italic">{video.notes}</p>
        )}
      </div>
    </button>
  )
}
