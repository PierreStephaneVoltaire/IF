import React, { useState } from 'react'
import { Stack, Text, Button, Group, Radio, Paper, Badge } from '@mantine/core'
import type { ImportPending, MergeStrategy } from '@powerlifting/types'
import { SessionDiff } from './SessionDiff'

interface Props {
  pendingImport: ImportPending | null
  onNext: () => void
  onPrev: () => void
}

export const Step5_ConflictResolve: React.FC<Props> = ({ pendingImport, onNext, onPrev }) => {
  const [strategy, setStrategy] = useState<MergeStrategy>('append')
  
  if (!pendingImport) return null

  if (pendingImport.import_type === 'template') {
    return (
      <Stack py="xl" align="center">
        <Text>Templates don't have date conflicts. You can proceed.</Text>
        <Group mt="xl">
          <Button variant="outline" onClick={onPrev}>Back</Button>
          <Button onClick={onNext}>Continue</Button>
        </Group>
      </Stack>
    )
  }

  const { ai_parse_result } = pendingImport
  // Extract diff from ai_parse_result if it exists (hypothetical structure)
  const diff = (ai_parse_result as any).diff || { new_sessions: [], conflicts: [], protected: [] }

  return (
    <Stack py="xl">
      <Paper withBorder p="md" bg="var(--mantine-color-gray-0)" radius="md">
        <Text weight={600} mb="xs">Overall Merge Strategy</Text>
        <Radio.Group value={strategy} onChange={(v) => setStrategy(v as MergeStrategy)}>
          <Group mt="xs">
            <Radio value="append" label="Append to end" />
            <Radio value="overwrite_future" label="Overwrite future sessions" />
            <Radio value="selective" label="Selective merge (manual)" />
          </Group>
        </Radio.Group>
      </Paper>

      {diff.conflicts.length > 0 && (
        <SessionDiff data={diff} />
      )}

      <Group position="apart" mt="xl">
        <Button variant="outline" onClick={onPrev}>Back</Button>
        <Button onClick={onNext}>Confirm Conflict Resolution</Button>
      </Group>
    </Stack>
  )
}
