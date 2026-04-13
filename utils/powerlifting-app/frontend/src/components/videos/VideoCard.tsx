import { Card, Center, Text, Box, UnstyledButton } from '@mantine/core'
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
    <UnstyledButton onClick={onClick} w="100%" style={{ textAlign: 'left' }}>
      <Card withBorder shadow="sm" padding={0} style={{ overflow: 'hidden' }}>
        {/* Thumbnail */}
        <Box
          pos="relative"
          style={{
            aspectRatio: '16 / 9',
            background: 'var(--mantine-color-gray-1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {hasThumbnail ? (
            <Box
              component="img"
              src={video.thumbnail_url}
              alt={video.exercise_name}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          ) : (
            <Center style={{ flexDirection: 'column', gap: 4 }}>
              <Play size={32} color="var(--mantine-color-gray-6)" />
              <Text size="xs" c="dimmed">Processing...</Text>
            </Center>
          )}
          <Box
            pos="absolute"
            inset={0}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              transition: 'background 150ms',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(0, 0, 0, 0.3)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <Play
              size={40}
              color="white"
              style={{ opacity: 0, transition: 'opacity 150ms' }}
            />
          </Box>
        </Box>

        {/* Info */}
        <Box p={12} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Text fw={600} size="sm">{video.exercise_name}</Text>
          <Text size="xs" c="dimmed">
            {session_date} · {day} · W{week_number} · {phase_name}
          </Text>
          {video.set_number && (
            <Text size="xs" c="dimmed">Set {video.set_number}</Text>
          )}
          {video.notes && (
            <Text size="xs" c="dimmed" fs="italic">{video.notes}</Text>
          )}
        </Box>
      </Card>
    </UnstyledButton>
  )
}
