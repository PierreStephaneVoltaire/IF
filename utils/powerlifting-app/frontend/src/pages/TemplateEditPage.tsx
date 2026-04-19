import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Save, X } from 'lucide-react'
import {
  Stack, Group, Title, Text, Button, Alert, LoadingOverlay, Divider,
} from '@mantine/core'
import { fetchTemplate, updateTemplate } from '../api/client'
import { TemplateMetaEditor } from '../components/templates/TemplateMetaEditor'
import { TemplatePhasesEditor } from '../components/templates/TemplatePhasesEditor'
import { TemplateSessionsEditor } from '../components/templates/TemplateSessionsEditor'
import type { Template } from '@powerlifting/types'

export default function TemplateEditPage() {
  const { sk } = useParams<{ sk: string }>()
  const navigate = useNavigate()
  const [template, setTemplate] = useState<Template | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sk) return
    fetchTemplate(sk)
      .then(setTemplate)
      .catch((e) => setError(e?.message ?? 'Failed to load template'))
      .finally(() => setLoading(false))
  }, [sk])

  async function handleSave() {
    if (!sk || !template) return
    if (!template.meta.name.trim()) {
      setError('Template name is required')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await updateTemplate(sk, template)
      navigate(`/designer/templates/${encodeURIComponent(sk)}`)
    } catch (e: any) {
      setError(e?.message ?? 'Failed to save template')
      setSaving(false)
    }
  }

  return (
    <Stack gap="lg" style={{ position: 'relative' }}>
      <LoadingOverlay visible={loading} />

      <Group justify="space-between">
        <Group gap="xs">
          <Text component={Link} to="/designer" size="sm" c="dimmed" style={{ textDecoration: 'none' }}>
            Designer
          </Text>
          <Text c="dimmed">/</Text>
          <Text component={Link} to="/designer/templates" size="sm" c="dimmed" style={{ textDecoration: 'none' }}>
            Template Library
          </Text>
          <Text c="dimmed">/</Text>
          <Title order={2}>{template?.meta.name ?? 'Edit Template'}</Title>
        </Group>
        <Group gap="xs">
          <Button
            variant="default"
            leftSection={<X size={16} />}
            onClick={() => navigate(`/designer/templates/${encodeURIComponent(sk)}`)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            leftSection={<Save size={16} />}
            onClick={handleSave}
            loading={saving}
            disabled={saving || !template}
          >
            Save
          </Button>
        </Group>
      </Group>

      {error && (
        <Alert color="red" title="Error">
          {error}
        </Alert>
      )}

      {template && (
        <Stack gap="lg">
          <Stack gap="sm">
            <Title order={3}>Details</Title>
            <TemplateMetaEditor
              meta={template.meta}
              onChange={(meta) => setTemplate(t => t ? { ...t, meta } : t)}
            />
          </Stack>

          <Divider />

          <Stack gap="sm">
            <Title order={3}>Phases</Title>
            <TemplatePhasesEditor
              phases={template.phases}
              onChange={(phases) => setTemplate(t => t ? { ...t, phases } : t)}
            />
          </Stack>

          <Divider />

          <Stack gap="sm">
            <Title order={3}>Sessions</Title>
            <TemplateSessionsEditor
              sessions={template.sessions}
              onChange={(sessions) => setTemplate(t => t ? { ...t, sessions } : t)}
            />
          </Stack>
        </Stack>
      )}
    </Stack>
  )
}
