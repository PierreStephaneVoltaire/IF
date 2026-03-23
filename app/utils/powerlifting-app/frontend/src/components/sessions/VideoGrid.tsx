import { useState } from 'react'
import { Play, Trash2, X, Loader2, Film, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { useUiStore } from '@/store/uiStore'
import { useProgramStore } from '@/store/programStore'
import * as api from '@/api/client'
import VideoPlayer from './VideoPlayer'
import type { Session, SessionVideo } from '@powerlifting/types'

interface VideoGridProps {
  session: Session
}

export default function VideoGrid({ session }: VideoGridProps) {
  const { pushToast } = useUiStore()
  const { version, removeSessionVideo } = useProgramStore()
  const [playingVideo, setPlayingVideo] = useState<SessionVideo | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const videos = session.videos || []

  async function handleDelete(video: SessionVideo) {
    if (!confirm('Delete this video?')) return

    setDeletingId(video.video_id)

    try {
      // Delete via backend API (handles S3 + DynamoDB)
      await api.removeSessionVideo(version, session.date, video.video_id)

      // Update local store
      removeSessionVideo(session.date, video.video_id)

      pushToast({ message: 'Video deleted', type: 'success' })
    } catch (err) {
      console.error('Failed to delete video:', err)
      pushToast({ message: 'Failed to delete video', type: 'error' })
    } finally {
      setDeletingId(null)
    }
  }

  if (videos.length === 0) {
    return null
  }

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {videos.map((video) => (
          <div
            key={video.video_id}
            className="group relative bg-card border border-border rounded-lg overflow-hidden"
          >
            {/* Thumbnail / Play Button */}
            <button
              onClick={() => setPlayingVideo(video)}
              className="relative w-full aspect-video bg-muted"
            >
              {video.thumbnail_status === 'pending' ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 text-muted-foreground animate-spin" />
                </div>
              ) : video.thumbnail_status === 'failed' ? (
                <div className="absolute inset-0 flex items-center justify-center bg-destructive/10">
                  <AlertCircle className="w-6 h-6 text-destructive" />
                </div>
              ) : video.thumbnail_url ? (
                <img
                  src={video.thumbnail_url}
                  alt={video.exercise_name || 'Video thumbnail'}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Film className="w-6 h-6 text-muted-foreground" />
                </div>
              )}

              {/* Play Overlay */}
              <div className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-black/40 transition-colors">
                <Play className="w-8 h-8 text-white" />
              </div>
            </button>

            {/* Info */}
            <div className="p-2">
              <p className="text-sm font-medium truncate">
                {video.exercise_name || 'Video'}
              </p>
              <div className="flex items-center justify-between">
                {video.set_number && (
                  <span className="text-xs text-muted-foreground">
                    Set {video.set_number}
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(video)
                  }}
                  disabled={deletingId === video.video_id}
                  className={clsx(
                    'p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity',
                    'hover:bg-destructive/10 hover:text-destructive',
                    deletingId === video.video_id && 'opacity-100'
                  )}
                >
                  {deletingId === video.video_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Video Player Modal */}
      {playingVideo && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="relative max-w-4xl w-full">
            <button
              onClick={() => setPlayingVideo(null)}
              className="absolute -top-10 right-0 p-2 text-white hover:bg-white/20 rounded"
            >
              <X className="w-6 h-6" />
            </button>

            <VideoPlayer
              src={playingVideo.video_url}
              thumbnailUrl={playingVideo.thumbnail_url}
              className="w-full"
            />

            {/* Video Info */}
            <div className="mt-2 text-white">
              <p className="font-medium">
                {playingVideo.exercise_name || 'Video'}
                {playingVideo.set_number && ` - Set ${playingVideo.set_number}`}
              </p>
              {playingVideo.notes && (
                <p className="text-sm text-white/70">{playingVideo.notes}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
