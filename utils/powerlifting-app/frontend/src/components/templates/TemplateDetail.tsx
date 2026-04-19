import React, { useState } from 'react'
import { Stack, Group, Title, Button, Text, Badge, Divider, LoadingOverlay } from '@mantine/core'
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
    <Stack spacing="xl">
      <LoadingOverlay visible={loading} />
      <Group position="apart">
        <Stack spacing={4}>
          <Group spacing="sm">
            <Title order={2}>{template.meta.name}</Title>
            {template.meta.archived && <Badge color="gray">Archived</Badge>}
          </Group>
          <Text size="sm" color="dimmed">
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

      <Group grow align="flex-start" breakpoints={[{ maxWidth: 'md', cols: 1 }]}>
        <Stack spacing="lg" style={{ flex: 2 }}>
          <Title order={3}>Sessions</Title>
          <SessionGrid template={template} />
        </Stack>
        
        <Stack spacing="lg" style={{ flex: 1 }}>
          <Title order={3}>AI Analysis</Title>
          <EvaluationPanel 
            sk={template.sk} 
            evaluation={template.meta.evaluation} 
            onRefresh={onRefresh}
          />
        </Stack>
      </Group>

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
