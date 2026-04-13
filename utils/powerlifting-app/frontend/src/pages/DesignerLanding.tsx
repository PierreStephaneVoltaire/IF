import { Link } from 'react-router-dom'
import { Card, SimpleGrid, Text, UnstyledButton, Group, Stack } from '@mantine/core'
import { GitBranch, ClipboardList } from 'lucide-react'

export default function DesignerLanding() {
  return (
    <Stack gap="md">
      <Text size="xl" fw={700}>Program Designer</Text>

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <UnstyledButton component={Link} to="/designer/phases">
          <Card withBorder shadow="sm" padding="lg">
            <Stack justify="space-between" h="100%">
              <div>
                <Group gap="sm" mb="sm">
                  <GitBranch size={24} />
                  <Text size="lg" fw={600}>Phase Design</Text>
                </Group>
                <Text size="sm" c="dimmed">
                  Manage training phases, set week ranges and RPE targets, and organize your training blocks.
                </Text>
              </div>
              <Text size="xs" c="blue" mt="md">Open phase designer →</Text>
            </Stack>
          </Card>
        </UnstyledButton>

        <UnstyledButton component={Link} to="/designer/sessions">
          <Card withBorder shadow="sm" padding="lg">
            <Stack justify="space-between" h="100%">
              <div>
                <Group gap="sm" mb="sm">
                  <ClipboardList size={24} />
                  <Text size="lg" fw={600}>Session Design</Text>
                </Group>
                <Text size="sm" c="dimmed">
                  Plan and manage training sessions by week, add exercises, and set planned sets and reps.
                </Text>
              </div>
              <Text size="xs" c="blue" mt="md">Open session designer →</Text>
            </Stack>
          </Card>
        </UnstyledButton>
      </SimpleGrid>
    </Stack>
  )
}
