import React from 'react'
import { Stack, Text, Group, Badge, Paper, SimpleGrid } from '@mantine/core'
import { format } from 'date-fns'

interface Props {
  data: {
    new_sessions: any[]
    conflicts: any[]
    protected: any[]
  }
}

export const SessionDiff: React.FC<Props> = ({ data }) => {
  return (
    <Stack spacing="xl">
      {data.new_sessions.length > 0 && (
        <Stack spacing="xs">
          <Badge color="green" size="lg">New Sessions ({data.new_sessions.length})</Badge>
          <SimpleGrid cols={3} breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>
            {data.new_sessions.map((s, i) => (
              <Paper key={i} withBorder p="xs" radius="sm">
                <Text size="sm" weight={500}>{format(new Date(s.date), 'MMM d, yyyy')}</Text>
                <Text size="xs" color="dimmed" lineClamp={1}>{s.exercises.map((e: any) => e.name).join(', ')}</Text>
              </Paper>
            ))}
          </SimpleGrid>
        </Stack>
      )}

      {data.conflicts.length > 0 && (
        <Stack spacing="xs">
          <Badge color="yellow" size="lg">Conflicts ({data.conflicts.length})</Badge>
          <SimpleGrid cols={2} breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>
            {data.conflicts.map((c, i) => (
              <Paper key={i} withBorder p="xs" radius="sm" style={{ borderLeft: '4px solid orange' }}>
                <Group position="apart">
                  <Text size="sm" weight={500}>{format(new Date(c.session_date), 'MMM d, yyyy')}</Text>
                  <Badge variant="outline" color="orange" size="xs">CONFLICT</Badge>
                </Group>
                <Group grow mt="xs">
                  <Stack spacing={0}>
                    <Text size="xs" color="dimmed">Existing</Text>
                    <Text size="xs" lineClamp={1}>{c.existing_label || '—'}</Text>
                  </Stack>
                  <Stack spacing={0}>
                    <Text size="xs" color="dimmed">Incoming</Text>
                    <Text size="xs" lineClamp={1}>{c.incoming_label || '—'}</Text>
                  </Stack>
                </Group>
              </Paper>
            ))}
          </SimpleGrid>
        </Stack>
      )}

      {data.protected.length > 0 && (
        <Stack spacing="xs">
          <Badge color="gray" size="lg">Protected (Locked) ({data.protected.length})</Badge>
          <Text size="xs" color="dimmed">These sessions have data that cannot be overwritten automatically.</Text>
          <SimpleGrid cols={3} breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>
            {data.protected.map((s, i) => (
              <Paper key={i} withBorder p="xs" radius="sm" style={{ opacity: 0.7 }}>
                <Text size="sm" weight={500}>{format(new Date(s.date), 'MMM d, yyyy')}</Text>
                <Text size="xs" color="dimmed" lineClamp={1}>{s.label}</Text>
              </Paper>
            ))}
          </SimpleGrid>
        </Stack>
      )}
    </Stack>
  )
}
