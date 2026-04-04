import { useState, useRef } from 'react'
import { Play, Pause, Maximize, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

interface VideoPlayerProps {
  src: string
  thumbnailUrl?: string
  className?: string
}

const PLAYBACK_SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2]

export default function VideoPlayer({
  src,
  thumbnailUrl,
  className,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [showControls, setShowControls] = useState(true)

  function togglePlay() {
    const video = videoRef.current
    if (!video) return

    if (isPlaying) {
      video.pause()
    } else {
      video.play()
    }
    setIsPlaying(!isPlaying)
  }

  function handleSpeedChange() {
    const video = videoRef.current
    if (!video) return

    const currentIndex = PLAYBACK_SPEEDS.indexOf(playbackSpeed)
    const nextIndex = (currentIndex + 1) % PLAYBACK_SPEEDS.length
    const newSpeed = PLAYBACK_SPEEDS[nextIndex]

    video.playbackRate = newSpeed
    setPlaybackSpeed(newSpeed)
  }

  function handleFullscreen() {
    const video = videoRef.current
    if (!video) return

    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      video.requestFullscreen()
    }
  }

  function handleLoadedData() {
    setIsLoading(false)
  }

  function handleWaiting() {
    setIsLoading(true)
  }

  function handleCanPlay() {
    setIsLoading(false)
  }

  return (
    <div
      className={clsx('relative group bg-black rounded-lg overflow-hidden', className)}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(true)}
    >
      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
          <Loader2 className="w-8 h-8 text-white animate-spin" />
        </div>
      )}

      {/* Video Element */}
      <video
        ref={videoRef}
        src={src}
        poster={thumbnailUrl}
        playsInline
        className="w-full aspect-video"
        onLoadedData={handleLoadedData}
        onWaiting={handleWaiting}
        onCanPlay={handleCanPlay}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onClick={togglePlay}
      />

      {/* Controls Overlay */}
      <div
        className={clsx(
          'absolute bottom-0 left-0 right-0 p-3',
          'bg-gradient-to-t from-black/80 to-transparent',
          'transition-opacity duration-200',
          showControls ? 'opacity-100' : 'opacity-0'
        )}
      >
        <div className="flex items-center justify-between gap-3">
          {/* Play/Pause */}
          <button
            onClick={togglePlay}
            className="p-2 bg-white/20 rounded-full hover:bg-white/30 transition-colors"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 text-white" />
            ) : (
              <Play className="w-5 h-5 text-white" />
            )}
          </button>

          {/* Playback Speed */}
          <button
            onClick={handleSpeedChange}
            className="px-2 py-1 bg-white/20 rounded text-white text-sm font-mono hover:bg-white/30 transition-colors"
          >
            {playbackSpeed}x
          </button>

          {/* Fullscreen */}
          <button
            onClick={handleFullscreen}
            className="p-2 bg-white/20 rounded-full hover:bg-white/30 transition-colors"
          >
            <Maximize className="w-5 h-5 text-white" />
          </button>
        </div>
      </div>
    </div>
  )
}
