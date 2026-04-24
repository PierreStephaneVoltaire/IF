import React, { useState } from 'react'
import { Stack, Group, Title, Button, Text, Badge, Divider, LoadingOverlay, Grid } from '@mantine/core'
import { Edit2 } from 'lucide-react'
import { Template, AiTemplateEvaluation } from '@powerlifting/types'
import { SessionGrid } from './SessionGrid'
import { EvaluationPanel } from './EvaluationPanel'
import { ApplyModal } from './ApplyModal'
import { MaxResolutionGate } from './MaxResolutionGate'
import { confirmApplyTemplate, fetchTemplate } from '../../api/client'
import { useNavigate } from 'react-router-dom'

interface Props {
  template: Template
  onRefresh: () => void
}

export const TemplateDetail: React.FC<Props> = ({ template, onRefresh }) => {
  const [applyModalOpened, setApplyModalOpened] = useState(false)
  const [missingMaxes, setMissingMaxes] = useState<string[] | null>(null)
  const [applyData, setApplyData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleApply = (res: any) => {
    if (res.missing_maxes && res.missing_maxes.length > 0) {
      setMissingMaxes(res.missing_maxes)
      setApplyData(res)
      setApplyModalOpened(false)
    } else {
      // Direct success
      navigate(`/designer/sessions?version=${res.program_version}`)
    }
  }

  const handleConfirmApply = async (backfilled_maxes: Record<string, number>) => {
    setLoading(true)
    try {
      const res = await confirmApplyTemplate(template.sk, {
        backfilled_maxes,
        start_date: applyData.start_date,
        week_start_day: applyData.week_start_day,
      })
      navigate(`/designer/sessions?version=${res.program_sk}`)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Stack gap="xl">
      <LoadingOverlay visible={loading} />
      <Group justify="space-between">
        <Stack gap={4}>
          <Group gap="sm">
            <Title order={2}>{template.meta.name}</Title>
            {template.meta.archived && <Badge color="gray">Archived</Badge>}
          </Group>
          <Text size="sm" c="dimmed">
            {template.meta.estimated_weeks} Weeks • {template.meta.days_per_week} Days/Week
          </Text>
        </Stack>
        
        <Group>
          <Button
            variant="default"
            leftSection={<Edit2 size={16} />}
            onClick={() => navigate(`/designer/templates/${encodeURIComponent(template.sk)}/edit`)}
          >
            Edit
          </Button>
          <Button size="lg" onClick={() => setApplyModalOpened(true)}>Apply Template</Button>
        </Group>
      </Group>

      <Divider />

      <Grid gap="lg" align="flex-start">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap="lg">
          <Title order={3}>Sessions</Title>
          <SessionGrid template={template} />
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack gap="lg">
          <Title order={3}>AI Analysis</Title>
          <EvaluationPanel 
            sk={template.sk} 
            evaluation={template.meta.ai_evaluation ?? null}
            onRefresh={onRefresh}
          />
          </Stack>
        </Grid.Col>
      </Grid>

      <ApplyModal 
        opened={applyModalOpened} 
        onClose={() => setApplyModalOpened(false)} 
        sk={template.sk}
        onApply={handleApply}
      />

      {missingMaxes && (
        <MaxResolutionGate 
          missingMaxes={missingMaxes}
          onResolved={handleConfirmApply}
          onCancel={() => setMissingMaxes(null)}
        />
      )}
    </Stack>
  )
}
