import { useState } from 'react'
import { X, Trash2 } from 'lucide-react'
import { useUiStore } from '@/store/uiStore'
import { useProgramStore } from '@/store/programStore'
import * as api from '@/api/client'
import type { VideoLibraryItem } from '@powerlifting/types'

interface VideoPlayerModalProps {
  item: VideoLibraryItem | null
  onClose: () => void
  onDeleted?: () => void
}

export default function VideoPlayerModal({ item, onClose, onDeleted }: VideoPlayerModalProps) {
  const { pushToast } = useUiStore()
  const { version } = useProgramStore()
  const [showConfirm, setShowConfirm] = useState(false)

  if (!item) return null

  const { video, session_date, day, week_number, phase_name } = item

  async function handleDelete() {
    try {
      await api.removeSessionVideo(version, session_date, video.video_id)
      pushToast({ message: 'Video deleted', type: 'success' })
      onDeleted?.()
      onClose()
    } catch (err) {
      console.error('Delete failed:', err)
      pushToast({ message: 'Failed to delete video', type: 'error' })
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100]"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div>
            <h3 className="font-semibold">{video.exercise_name}</h3>
            <p className="text-xs text-muted-foreground">
              {session_date} · {day} · W{week_number} · {phase_name}
            </p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-accent rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Video */}
        <div className="bg-black">
          <video
            src={video.video_url}
            controls
            autoPlay
            className="w-full max-h-[70vh]"
          />
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-border space-y-2">
          {video.notes && (
            <p className="text-sm italic text-muted-foreground">{video.notes}</p>
          )}
          <div className="flex justify-end">
            {showConfirm ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowConfirm(false)}
                  className="px-3 py-1.5 text-sm bg-secondary rounded-md"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm bg-destructive text-destructive-foreground rounded-md"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Confirm Delete
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowConfirm(true)}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 rounded-md"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Video
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
