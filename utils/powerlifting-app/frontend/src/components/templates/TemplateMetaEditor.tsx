import { Stack, TextInput, Textarea, NumberInput } from '@mantine/core'
import type { TemplateMeta } from '@powerlifting/types'

interface Props {
  meta: TemplateMeta
  onChange: (meta: TemplateMeta) => void
}

export function TemplateMetaEditor({ meta, onChange }: Props) {
  return (
    <Stack gap="md">
      <TextInput
        label="Name"
        value={meta.name}
        onChange={(e) => onChange({ ...meta, name: e.currentTarget.value })}
      />
      <Textarea
        label="Description"
        value={meta.description}
        onChange={(e) => onChange({ ...meta, description: e.currentTarget.value })}
        autosize
        minRows={2}
      />
      <NumberInput
        label="Estimated Weeks"
        value={meta.estimated_weeks}
        onChange={(v) => onChange({ ...meta, estimated_weeks: Number(v) || 1 })}
        min={1}
      />
      <NumberInput
        label="Days Per Week"
        value={meta.days_per_week}
        onChange={(v) => onChange({ ...meta, days_per_week: Number(v) || 1 })}
        min={1}
        max={7}
      />
    </Stack>
  )
}
