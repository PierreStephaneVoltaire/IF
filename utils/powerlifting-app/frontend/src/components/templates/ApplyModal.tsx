import React, { useState } from 'react'
import { Modal, Select, Button, Stack, Group, Text, Radio } from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import { applyTemplate } from '../../api/client'

interface Props {
  opened: boolean
  onClose: () => void
  sk: string
  onApply: (data: any) => void
}

export const ApplyModal: React.FC<Props> = ({ opened, onClose, sk, onApply }) => {
  const [target, setTarget] = useState<string>('new_block')
  const [startDate, setStartDate] = useState<Date | null>(new Date())
  const [weekStartDay, setWeekStartDay] = useState<string>('Monday')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    setLoading(true)
    try {
      const res = await applyTemplate(sk, {
        target,
        start_date: startDate?.toISOString().split('T')[0],
        week_start_day: weekStartDay,
      })
      onApply(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Apply Template" size="md">
      <Stack spacing="md">
        <Select 
          label="Apply Strategy" 
          value={target}
          onChange={(v) => setTarget(v || 'new_block')}
          data={[
            { value: 'new_block', label: 'Create new training block' },
            { value: 'append', label: 'Append to current block' },
            { value: 'replace_incomplete', label: 'Replace non-completed sessions' },
          ]}
        />

        <DatePickerInput 
          label="Start Date" 
          placeholder="Pick date" 
          value={startDate} 
          onChange={setStartDate} 
        />

        <Radio.Group 
          label="Week Start Day" 
          value={weekStartDay} 
          onChange={setWeekStartDay}
        >
          <Group mt="xs">
            <Radio value="Monday" label="Monday" />
            <Radio value="Sunday" label="Sunday" />
          </Group>
        </Radio.Group>

        <Group position="right" mt="xl">
          <Button variant="subtle" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Apply</Button>
        </Group>
      </Stack>
    </Modal>
  )
}
