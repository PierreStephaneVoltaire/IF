import { useState, useEffect, useCallback } from 'react'
import { Film, Calendar } from 'lucide-react'
import { Select, SimpleGrid, Loader, Paper, Stack, Text, Group, Button, Center, Box } from '@mantine/core'
import { useProgramStore } from '@/store/programStore'
import * as api from '@/api/client'
import VideoCard from '@/components/videos/VideoCard'
import VideoPlayerModal from '@/components/videos/VideoPlayerModal'
import type { VideoLibraryItem } from '@powerlifting/types'

export default function VideosPage() {
  const { version } = useProgramStore()
  const [videos, setVideos] = useState<VideoLibraryItem[]>([])
  const [exercises, setExercises] = useState<string[]>([])
  const [exerciseFilter, setExerciseFilter] = useState<string | null>(null)
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
    <Stack gap="md" maw={672} mx="auto" p="md">
      {/* Header */}
      <Group gap="xs">
        <Film size={20} />
        <Text size="xl" fw={700}>Videos</Text>
        {videos.length > 0 && (
          <Text size="sm" c="dimmed">({videos.length})</Text>
        )}
      </Group>

      {/* Filters */}
      {exercises.length > 0 && (
        <Group gap="xs">
          <Select
            value={exerciseFilter}
            onChange={setExerciseFilter}
            data={[
              { value: '', label: 'All exercises' },
              ...exercises.map((name) => ({ value: name, label: name })),
            ]}
            clearable={false}
            w={200}
          />
          <Button
            variant="default"
            size="xs"
            onClick={() => setSortOrder(sortOrder === 'newest' ? 'oldest' : 'newest')}
            title={sortOrder === 'newest' ? 'Show oldest first' : 'Show newest first'}
          >
            {sortOrder === 'newest' ? 'Newest' : 'Oldest'}
          </Button>
        </Group>
      )}

      {/* Loading */}
      {isLoading && (
        <Center py={80}>
          <Loader size="sm" />
        </Center>
      )}

      {/* Empty State */}
      {!isLoading && videos.length === 0 && (
        <Center py={80}>
          <Stack align="center" gap="xs">
            <Film size={48} />
            <Text fw={500} c="dimmed">No videos uploaded yet</Text>
            <Box
              component="a"
              href="/calendar"
              style={{ textDecoration: 'none' }}
            >
              <Group gap={4}>
                <Calendar size={14} />
                <Text size="sm" c="blue">Go to Calendar</Text>
              </Group>
            </Box>
          </Stack>
        </Center>
      )}

      {/* Feed */}
      {!isLoading && videos.length > 0 && (
        <Stack gap="sm">
          {videos.map((item) => (
            <Paper key={item.video.video_id} withBorder>
              <VideoCard
                item={item}
                onClick={() => setSelectedItem(item)}
              />
            </Paper>
          ))}
        </Stack>
      )}

      {/* Player Modal */}
      <VideoPlayerModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onDeleted={loadVideos}
      />
    </Stack>
  )
}
