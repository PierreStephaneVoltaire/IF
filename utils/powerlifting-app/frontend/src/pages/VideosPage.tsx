import { useState, useEffect, useCallback } from 'react'
import { Filter, ArrowUpDown, Film, Calendar } from 'lucide-react'
import { useProgramStore } from '@/store/programStore'
import * as api from '@/api/client'
import VideoCard from '@/components/videos/VideoCard'
import VideoPlayerModal from '@/components/videos/VideoPlayerModal'
import type { VideoLibraryItem } from '@powerlifting/types'

export default function VideosPage() {
  const { version } = useProgramStore()
  const [videos, setVideos] = useState<VideoLibraryItem[]>([])
  const [exercises, setExercises] = useState<string[]>([])
  const [exerciseFilter, setExerciseFilter] = useState('')
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest')
  const [isLoading, setIsLoading] = useState(true)
  const [selectedItem, setSelectedItem] = useState<VideoLibraryItem | null>(null)

  const loadVideos = useCallback(async () => {
    setIsLoading(true)
    try {
      const result = await api.getVideos(version, exerciseFilter || undefined, sortOrder)
      setVideos(result.videos)
      setExercises(result.exercises)
    } catch (err) {
      console.error('Failed to load videos:', err)
    } finally {
      setIsLoading(false)
    }
  }, [version, exerciseFilter, sortOrder])

  useEffect(() => {
    loadVideos()
  }, [loadVideos])

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Film className="w-5 h-5" />
          Videos
          {videos.length > 0 && (
            <span className="text-sm font-normal text-muted-foreground">({videos.length})</span>
          )}
        </h1>
      </div>

      {/* Filters */}
      {exercises.length > 0 && (
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <select
            value={exerciseFilter}
            onChange={(e) => setExerciseFilter(e.target.value)}
            className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
          >
            <option value="">All exercises</option>
            {exercises.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <button
            onClick={() => setSortOrder(sortOrder === 'newest' ? 'oldest' : 'newest')}
            className="flex items-center gap-1 px-3 py-1.5 border border-border rounded-md bg-background text-sm hover:bg-accent"
            title={sortOrder === 'newest' ? 'Show oldest first' : 'Show newest first'}
          >
            <ArrowUpDown className="w-4 h-4" />
            {sortOrder === 'newest' ? 'Newest' : 'Oldest'}
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          Loading videos...
        </div>
      )}

      {/* Empty State */}
      {!isLoading && videos.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-2">
          <Film className="w-12 h-12" />
          <p className="font-medium">No videos uploaded yet</p>
          <a href="/calendar" className="text-sm text-primary hover:underline flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            Go to Calendar
          </a>
        </div>
      )}

      {/* Feed */}
      {!isLoading && videos.length > 0 && (
        <div className="space-y-3">
          {videos.map((item) => (
            <VideoCard
              key={item.video.video_id}
              item={item}
              onClick={() => setSelectedItem(item)}
            />
          ))}
        </div>
      )}

      {/* Player Modal */}
      <VideoPlayerModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onDeleted={loadVideos}
      />
    </div>
  )
}
