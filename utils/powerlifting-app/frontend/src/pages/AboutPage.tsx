import {
  Stack,
  Title,
  Text,
  Paper,
  Group,
  List,
  ThemeIcon,
  Divider,
  Table,
  Badge,
  Alert,
  Button,
  Center,
  SimpleGrid,
  Container,
} from '@mantine/core'
import {
  Info,
  Activity,
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Zap,
  ShieldCheck,
  Globe,
  Database,
  Calculator,
} from 'lucide-react'
import { FORMULA_DESCRIPTIONS } from '@/constants/formulaDescriptions'

export default function AboutPage() {
  return (
    <Container size="lg" py="xl">
      <Stack gap="xl">
        {/* Header Section */}
        <Stack gap="xs">
          <Group gap="sm">
            <Activity size={32} color="var(--mantine-color-blue-filled)" />
            <Title order={1}>About the Peaking Portal</Title>
          </Group>
          <Text size="lg" c="dimmed" maw={800}>
            A statistical analysis engine designed to quantify peaking program effectiveness and maximize
            powerlifting competition performance. This is not a coaching app; it is a data-driven laboratory
            for the serious lifter.
          </Text>
        </Stack>

        <Divider />

        {/* Methodology & Mission */}
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
          <Stack gap="md">
            <Title order={2} size="h3">Our Mission</Title>
            <Text>
              The Peaking Portal aims to bridge the gap between "feel-based" training and objective
              statistical analysis. By aggregating session data, biometrics, and historical performance,
              we provide a granular view of how a peaking block actually transforms your strength.
            </Text>
            <Alert icon={<ShieldCheck size={16} />} color="blue" title="Data Philosophy">
              We balance necessity with friction. We don't ask for tedious metrics like continuous heart rate
              or daily macro tracking. We focus on high-signal data: loads, RPE, bodyweight, and perceived fatigue.
            </Alert>
          </Stack>
          <Stack gap="md">
            <Title order={2} size="h3">Analysis Core</Title>
            <Text>
              Our analysis is powered by two engines:
            </Text>
            <List
              spacing="xs"
              size="sm"
              center
              icon={
                <ThemeIcon color="blue" size={20} radius="xl">
                  <Zap size={12} />
                </ThemeIcon>
              }
            >
              <List.Item>
                <b>Statistical Engine:</b> Handles DOTS, ACWR, INOL, and Theil-Sen regressions.
              </List.Item>
              <List.Item>
                <b>AI Reasoning Layer:</b> Estimates fatigue dimensions (Axial, Neural, Peripheral, Systemic)
                based on exercise mechanics and provides qualitative program evaluation.
              </List.Item>
            </List>
          </Stack>
        </SimpleGrid>

        <Divider />

        {/* Detailed Formula Section */}
        <Stack gap="lg">
          <Group gap="sm">
            <Calculator size={24} />
            <Title order={2}>Mathematical Methodology</Title>
          </Group>

          {FORMULA_DESCRIPTIONS.map((f) => (
            <Paper key={f.id} withBorder p="xl" radius="md">
              <Stack gap="md">
                <Group justify="space-between" align="flex-start">
                  <div>
                    <Title order={3} size="h4">{f.title}</Title>
                    <Text size="sm" c="dimmed" mt={4}>{f.summary}</Text>
                  </div>
                  <Badge variant="light">Formula ID: {f.id}</Badge>
                </Group>

                <Paper withBorder p="md" bg="var(--mantine-color-gray-0)" style={{ borderLeft: '4px solid var(--mantine-color-blue-filled)' }}>
                  <Text ff="monospace" style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                    {f.formula}
                  </Text>
                </Paper>

                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                  <div>
                    <Text fw={600} size="xs" tt="uppercase" c="dimmed" mb={8}>Variables & Parameters</Text>
                    <Table fz="xs">
                      <Table.Tbody>
                        {f.variables.map((v) => (
                          <Table.Tr key={v.name}>
                            <Table.Td fw={700} w={80}>{v.name}</Table.Td>
                            <Table.Td>{v.description}</Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </div>
                  {f.thresholds && (
                    <div>
                      <Text fw={600} size="xs" tt="uppercase" c="dimmed" mb={8}>Thresholds & Interpretation</Text>
                      <Stack gap={4}>
                        {f.thresholds.map((t) => (
                          <Group key={t.label} gap="xs">
                            <Badge size="xs" variant="outline">{t.label}</Badge>
                            <Text size="xs"><b>{t.value}</b>: {t.flag}</Text>
                          </Group>
                        ))}
                      </Stack>
                    </div>
                  )}
                </SimpleGrid>
              </Stack>
            </Paper>
          ))}
        </Stack>

        <Divider />

        {/* Imperfections & Context */}
        <Stack gap="md">
          <Group gap="sm">
            <AlertTriangle size={24} color="var(--mantine-color-yellow-filled)" />
            <Title order={2}>Known Imperfections & Limitations</Title>
          </Group>
          <Text>
            No statistical model is perfect. Our analysis currently contains the following biases and omissions:
          </Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            <Paper withBorder p="md">
              <Text fw={600} size="sm" mb={4}>Chronobiology & Hormones</Text>
              <Text size="sm" c="dimmed">
                Users are typically stronger in the evening due to hormonal peaks, yet competitions often
                start in the morning. Our model does not yet account for training time vs. competition flight timing.
              </Text>
            </Paper>
            <Paper withBorder p="md">
              <Text fw={600} size="sm" mb={4}>Supplementation & Recovery</Text>
              <Text size="sm" c="dimmed">
                Stimulants (caffeine, pre-workouts) and ergogenic aids (creatine) significantly impact
                acute performance and recovery, but are currently excluded from mathematical dimensions.
              </Text>
            </Paper>
            <Paper withBorder p="md">
              <Text fw={600} size="sm" mb={4}>Biometric Precision</Text>
              <Text size="sm" c="dimmed">
                While we capture limb lengths, the interaction between bone length and lift style (e.g.,
                wide-sumo vs conventional) is estimated by AI rather than a rigid physical engine.
              </Text>
            </Paper>
            <Paper withBorder p="md">
              <Text fw={600} size="sm" mb={4}>Budget Constraints</Text>
              <Text size="sm" c="dimmed">
                We explicitly avoid computer vision/video analysis to keep the portal accessible and cost-effective.
                Technical breakdowns are inferred from velocity loss (estimated via RPE) and failure rates.
              </Text>
            </Paper>
          </SimpleGrid>
        </Stack>

        <Divider />

        {/* Future Roadmap */}
        <Stack gap="md">
          <Group gap="sm">
            <TrendingUp size={24} color="var(--mantine-color-green-filled)" />
            <Title order={2}>The Roadmap</Title>
          </Group>

          <Paper withBorder p="xl" bg="var(--mantine-color-blue-light)">
            <Stack gap="lg">
              <Group gap="lg">
                <Stack gap={4} align="center">
                  <Globe size={32} />
                  <Text size="xs" fw={700}>OpenPowerlifting</Text>
                </Stack>
                <Text size="sm">
                  <b>Comparative Benchmarking:</b> We will integrate OpenPowerlifting datasets to compare your
                  readiness against regional, national, and global populations over the last 1-5 years,
                  filtered by federation and weight class.
                </Text>
              </Group>

              <Group gap="lg">
                <Stack gap={4} align="center">
                  <Database size={32} />
                  <Text size="xs" fw={700}>Demographics</Text>
                </Stack>
                <Text size="sm">
                  <b>Age & Sex Normalization:</b> Future versions will adjust e1RM and DOTS trajectories
                  based on age-graded performance curves and sex-specific recovery profiles.
                </Text>
              </Group>

              <Group gap="lg">
                <Stack gap={4} align="center">
                  <BarChart3 size={32} />
                  <Text size="xs" fw={700}>In-Session Ad Hoc</Text>
                </Stack>
                <Text size="sm">
                  <b>Real-time Adjustments:</b> Dynamic session alteration logic to suggest weight or exercise
                  changes mid-workout based on acute fatigue, failed sets, or minor injuries.
                </Text>
              </Group>
            </Stack>
          </Paper>
        </Stack>

        <Divider />

        {/* Footer info */}
        <Center pb="xl">
          <Text size="xs" c="dimmed" ta="center">
            Developed for statistical analysis of peaking programs. <br />
            Data is strictly used for performance modeling and visualization.
          </Text>
        </Center>
      </Stack>
    </Container>
  )
}
