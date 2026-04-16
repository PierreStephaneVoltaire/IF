import React from 'react'
import { Card, Text, Stack, Group, Badge, List, Button, Loader } from '@mantine/core'
import { AiTemplateEvaluation } from '@powerlifting/types'
import { evaluateTemplate } from '../../api/client'

interface Props {
  sk: string
  evaluation?: AiTemplateEvaluation | null
  onRefresh: () => void
}

export const EvaluationPanel: React.FC<Props> = ({ sk, evaluation, onRefresh }) => {
  const [loading, setLoading] = React.useState(false)

  const handleEvaluate = async () => {
    setLoading(true)
    try {
      await evaluateTemplate(sk)
      onRefresh()
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (!evaluation && !loading) {
    return (
      <Card withBorder padding="lg" radius="md">
        <Stack align="center" spacing="md">
          <Text color="dimmed">No evaluation available yet.</Text>
          <Button onClick={handleEvaluate}>Generate AI Evaluation</Button>
        </Stack>
      </Card>
    )
  }

  if (loading) {
    return (
      <Card withBorder padding="lg" radius="md">
        <Stack align="center" spacing="md">
          <Loader />
          <Text>AI is analyzing the program...</Text>
        </Stack>
      </Card>
    )
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Stack spacing="md">
        <Group position="apart">
          <Text weight={700} size="lg">AI Evaluation</Text>
          <Badge color={evaluation?.stance === 'Recommended' ? 'green' : 'yellow'} size="lg">
            {evaluation?.stance || 'N/A'}
          </Badge>
        </Group>

        <Text size="sm">{evaluation?.summary}</Text>

        <Group grow align="flex-start">
          <Stack spacing="xs">
            <Text weight={600} size="sm" color="green">Strengths</Text>
            <List size="xs">
              {evaluation?.strengths.map((s, i) => <List.Item key={i}>{s}</List.Item>)}
            </List>
          </Stack>
          <Stack spacing="xs">
            <Text weight={600} size="sm" color="red">Weaknesses</Text>
            <List size="xs">
              {evaluation?.weaknesses.map((s, i) => <List.Item key={i}>{s}</List.Item>)}
            </List>
          </Stack>
        </Group>

        <Stack spacing="xs">
          <Text weight={600} size="sm" color="blue">Suggestions</Text>
          <List size="xs">
            {evaluation?.suggestions.map((s, i) => <List.Item key={i}>{s}</List.Item>)}
          </List>
        </Stack>

        <Button variant="subtle" size="xs" onClick={handleEvaluate} loading={loading}>
          Re-evaluate
        </Button>
      </Stack>
    </Card>
  )
}
