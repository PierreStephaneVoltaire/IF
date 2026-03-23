import { useState, useRef } from 'react'
import { X, Upload, Film, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useUiStore } from '@/store/uiStore'
import { useProgramStore } from '@/store/programStore'
import {
  uploadVideo,
  isValidVideoType,
  formatFileSize,
  MAX_VIDEO_SIZE,
} from '@/utils/s3'
import type { Session, SessionVideo } from '@powerlifting/types'

interface VideoUploadModalProps {
  session: Session
  isOpen: boolean
  onClose: () => void
  onUploaded: (video: SessionVideo) => void
}

export default function VideoUploadModal({
  session,
  isOpen,
  onClose,
  onUploaded,
}: VideoUploadModalProps) {
  const { pushToast } = useUiStore()
  const { version } = useProgramStore()
  const [file, setFile] = useState<File | null>(null)
  const [exerciseName, setExerciseName] = useState<string>('')
  const [setNumber, setSetNumber] = useState<number | undefined>()
  const [notes, setNotes] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOpen) return null

  const exerciseOptions = session.exercises.map((e) => e.name)

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return

    if (!isValidVideoType(selectedFile)) {
      pushToast({
        message: 'Invalid file type. Please use MP4, MOV, or WebM.',
        type: 'error',
      })
      return
    }

    if (selectedFile.size > MAX_VIDEO_SIZE) {
      pushToast({
        message: `File too large. Maximum size is ${formatFileSize(MAX_VIDEO_SIZE)}.`,
        type: 'error',
      })
      return
    }

    setFile(selectedFile)
  }

  async function handleUpload() {
    if (!file) return

    setIsUploading(true)
    setUploadProgress(0)

    try {
      // Upload via backend API (server proxy)
      const { video } = await uploadVideo(version, {
        file,
        sessionDate: session.date,
        exerciseName: exerciseName || undefined,
        setNumber,
        notes: notes || undefined,
        onProgress: setUploadProgress,
      })

      pushToast({ message: 'Video uploaded successfully', type: 'success' })
      onUploaded(video)
      onClose()
    } catch (err) {
      console.error('Upload failed:', err)
      pushToast({ message: 'Failed to upload video', type: 'error' })
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100]"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="font-semibold">Upload Video</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-accent rounded"
            disabled={isUploading}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* File Input */}
          <div>
            <label className="text-sm text-muted-foreground">Video File</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/quicktime,video/webm"
              onChange={handleFileSelect}
              className="hidden"
              disabled={isUploading}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className={clsx(
                'w-full mt-1 p-4 border-2 border-dashed border-border rounded-lg',
                'flex flex-col items-center gap-2',
                file ? 'border-primary bg-primary/5' : 'hover:border-primary/50 hover:bg-accent/50',
                isUploading && 'opacity-50 cursor-not-allowed'
              )}
            >
              <Film className="w-8 h-8 text-muted-foreground" />
              {file ? (
                <div className="text-center">
                  <p className="font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(file.size)}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Click to select a video (MP4, MOV, WebM)
                </p>
              )}
            </button>
          </div>

          {/* Exercise Dropdown */}
          <div>
            <label className="text-sm text-muted-foreground">Exercise (optional)</label>
            <select
              value={exerciseName}
              onChange={(e) => setExerciseName(e.target.value)}
              disabled={isUploading}
              className="w-full mt-1 px-3 py-2 border border-border rounded-md bg-background"
            >
              <option value="">Select exercise...</option>
              {exerciseOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          {/* Set Number */}
          <div>
            <label className="text-sm text-muted-foreground">Set Number (optional)</label>
            <input
              type="number"
              min={1}
              value={setNumber || ''}
              onChange={(e) => setSetNumber(e.target.value ? parseInt(e.target.value) : undefined)}
              disabled={isUploading}
              placeholder="e.g., 1, 2, 3..."
              className="w-full mt-1 px-3 py-2 border border-border rounded-md bg-background"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="text-sm text-muted-foreground">Notes (optional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={isUploading}
              placeholder="Form notes, observations..."
              className="w-full mt-1 px-3 py-2 border border-border rounded-md bg-background"
            />
          </div>

          {/* Upload Progress */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Uploading...</span>
                <span className="font-mono">{uploadProgress}%</span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="px-4 py-2 bg-secondary rounded-md disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Upload
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
