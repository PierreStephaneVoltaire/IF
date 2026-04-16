import React from 'react'
import { SimpleGrid, Paper, Text, Stack, Group, Badge } from '@mantine/core'
import { Template, Session } from '@powerlifting/types'
import { LoadTypeBadge } from '../shared/LoadTypeBadge'

interface Props {
  template: Template
}

export const SessionGrid: React.FC<Props> = ({ template }) => {
  const weeks = [...new Set(template.sessions.map(s => s.week || 0))].sort((a, b) => a - b)
  
  return (
    <Stack spacing="xl">
      {weeks.map(week => {
        const weekSessions = template.sessions.filter(s => s.week === week).sort((a, b) => (a.day_of_week || 0) - (b.day_of_week || 0))
        
        return (
          <Stack key={week} spacing="sm">
            <Text weight={700} size="lg">Week {week}</Text>
            <SimpleGrid cols={3} breakpoints={[{ maxWidth: 'md', cols: 1 }, { maxWidth: 'lg', cols: 2 }]}>
              {weekSessions.map((session, idx) => (
                <Paper key={idx} withBorder p="md" radius="md">
                  <Stack spacing="xs">
                    <Group position="apart">
                      <Text weight={500}>Day {session.day_of_week || '?'}</Text>
                      {session.label && <Badge variant="light">{session.label}</Badge>}
                    </Group>
                    
                    {session.exercises.map((ex, exIdx) => (
                      <Group key={exIdx} position="apart" noWrap spacing="xs">
                        <Stack spacing={0} style={{ flex: 1, minWidth: 0 }}>
                          <Text size="sm" truncate>{ex.name}</Text>
                          <Text size="xs" color="dimmed">
                            {ex.sets}x{ex.reps}
                            {ex.rpe_target && ` @ RPE ${ex.rpe_target}`}
                            {ex.percentage_target && ` (${(ex.percentage_target * 100).toFixed(0)}%)`}
                            {ex.load_kg ? ` ${ex.load_kg}kg` : ''}
                          </Text>
                        </Stack>
                        {ex.load_source && <LoadTypeBadge source={ex.load_source} />}
                      </Group>
                    ))}
                  </Stack>
                </Paper>
              ))}
            </SimpleGrid>
          </Stack>
        )
      })}
    </Stack>
  )
}
