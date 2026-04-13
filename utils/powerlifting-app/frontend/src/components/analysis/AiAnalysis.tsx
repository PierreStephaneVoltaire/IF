import { useState, useEffect } from 'react';
import { useProgramStore } from '@/store/programStore';
import { fetchCorrelationReport, fetchProgramEvaluation, type CorrelationReport, type ProgramEvaluationReport } from '@/api/analytics';
import { Paper, Group, Text, Badge, Button, Loader, Box, Table, Stack, SimpleGrid } from '@mantine/core';
import { Brain, RefreshCw, Trophy } from 'lucide-react';

const CORR_DIR_BADGE: Record<string, string> = {
  positive: 'green',
  negative: 'red',
  unclear: 'gray',
};

const CORR_STRENGTH_BADGE: Record<string, string> = {
  strong: 'violet',
  moderate: 'blue',
  weak: 'gray',
};

interface AiAnalysisProps {
  effectiveWeeks: number;
  weeksMode: number | 'block';
}

export function AiAnalysis({ effectiveWeeks, weeksMode }: AiAnalysisProps) {
  const { program } = useProgramStore();

  // Correlation report state
  const [corrReport, setCorrReport] = useState<CorrelationReport | null>(null);
  const [corrLoading, setCorrLoading] = useState(false);
  const [corrError, setCorrError] = useState<string | null>(null);

  // Program evaluation state
  const [evalReport, setEvalReport] = useState<ProgramEvaluationReport | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  // Fetch correlation report when weeks >= 4
  useEffect(() => {
    if (effectiveWeeks < 4) {
      setCorrReport(null);
      return;
    }
    setCorrLoading(true);
    setCorrError(null);
    fetchCorrelationReport(effectiveWeeks, 'current')
      .then(setCorrReport)
      .catch((e) => setCorrError(e.message))
      .finally(() => setCorrLoading(false));
  }, [effectiveWeeks]);

  const refreshCorrelation = () => {
    if (effectiveWeeks < 4) return;
    setCorrLoading(true);
    setCorrError(null);
    setCorrReport(null);
    import('@/api/analytics').then(({ fetchCorrelationReport }) => {
      const apiBase = import.meta.env.VITE_API_BASE_URL || '/fitness/api';
      fetch(`${apiBase}/analytics/correlation?weeks=${effectiveWeeks}&block=current&refresh=true`)
        .then(r => r.json())
        .then(body => {
          if (body.error) throw new Error(body.error);
          setCorrReport(body.data);
        })
        .catch((e) => setCorrError(e.message))
        .finally(() => setCorrLoading(false));
    });
  };

  // Program evaluation — fetch when in Full Block mode
  useEffect(() => {
    if (weeksMode !== 'block') {
      setEvalReport(null);
      setEvalError(null);
      return;
    }
    const completedCount = program?.sessions?.filter(s => (s.block ?? 'current') === 'current' && s.completed).length ?? 0;
    if (completedCount < 4) {
      setEvalReport(null);
      return;
    }
    setEvalLoading(true);
    setEvalError(null);
    fetchProgramEvaluation(false)
      .then(setEvalReport)
      .catch((e) => setEvalError(e.message))
      .finally(() => setEvalLoading(false));
  }, [weeksMode, program?.meta?.program_start, program?.sessions]);

  const refreshEvaluation = () => {
    if (weeksMode !== 'block') return;
    setEvalLoading(true);
    setEvalError(null);
    setEvalReport(null);
    fetchProgramEvaluation(true)
      .then(setEvalReport)
      .catch((e) => setEvalError(e.message))
      .finally(() => setEvalLoading(false));
  };

  const STANCE_COLORS: Record<string, string> = { continue: 'green', monitor: 'blue', adjust: 'yellow', critical: 'red' };
  const ALIGN_COLORS: Record<string, string> = { good: 'green', mixed: 'yellow', poor: 'red' };
  const PRIORITY_COLORS: Record<string, string> = { low: 'gray', moderate: 'yellow', high: 'red' };

  const completedCount = program?.sessions?.filter(s => (s.block ?? 'current') === 'current' && s.completed).length ?? 0;

  return (
    <>
      <Paper withBorder p="md">
        <Group justify="space-between" mb="sm">
          <Group gap="xs">
            <Brain size={18} />
            <Text fw={500}>Exercise ROI Correlation</Text>
            {corrReport && (
              <Badge color={corrReport.cached ? 'blue' : 'green'} variant="light" size="sm">
                {corrReport.cached ? `Cached ${corrReport.generated_at ? new Date(corrReport.generated_at).toLocaleDateString() : ''}` : 'Just generated'}
              </Badge>
            )}
          </Group>
          {effectiveWeeks >= 4 && (
            <Button
              variant="subtle"
              size="xs"
              onClick={refreshCorrelation}
              disabled={corrLoading}
              leftSection={<RefreshCw size={14} style={corrLoading ? { animation: 'spin 1s linear infinite' } : undefined} />}
            >
              Regenerate
            </Button>
          )}
        </Group>

        {effectiveWeeks < 4 ? (
          <Text size="sm" c="dimmed">Correlation analysis requires at least 4 weeks of data. Select 4+ weeks or Full Block.</Text>
        ) : corrLoading ? (
          <Group gap="xs" py="md">
            <Loader size="xs" />
            <Text size="sm" c="dimmed">Analyzing training data with AI...</Text>
          </Group>
        ) : corrError ? (
          <Text size="sm" c="red">{corrError}</Text>
        ) : corrReport ? (
          <>
            {corrReport.insufficient_data ? (
              <Text size="sm" c="dimmed">{corrReport.insufficient_data_reason || 'Insufficient data for meaningful correlation analysis.'}</Text>
            ) : (
              <>
                {corrReport.summary && (
                  <Text size="sm" c="dimmed" mb="md" p="sm" fs="italic" style={{ background: 'var(--mantine-color-default-hover)', borderRadius: 'var(--mantine-radius-sm)' }}>{corrReport.summary}</Text>
                )}
                {corrReport.findings.length > 0 ? (
                  <Box style={{ overflowX: 'auto' }}>
                    <Table fz="sm">
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th ta="left">Exercise</Table.Th>
                          <Table.Th ta="left">→ Lift</Table.Th>
                          <Table.Th ta="left" w={{ base: 'auto', sm: 100 }}>Direction</Table.Th>
                          <Table.Th ta="left" w={{ base: 'auto', sm: 100 }}>Strength</Table.Th>
                          <Table.Th ta="left" visibleFrom="sm">Reasoning</Table.Th>
                          <Table.Th ta="left" visibleFrom="sm">Caveat</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {corrReport.findings.map((f, i) => (
                          <Table.Tr key={i} style={{ verticalAlign: 'top' }}>
                            <Table.Td fw={500}>{f.exercise}</Table.Td>
                            <Table.Td>{f.lift}</Table.Td>
                            <Table.Td>
                              <Badge size="xs" variant="light" color={CORR_DIR_BADGE[f.correlation_direction] || 'gray'} style={{ textTransform: 'capitalize' }}>
                                {f.correlation_direction}
                              </Badge>
                            </Table.Td>
                            <Table.Td>
                              <Badge size="xs" variant="light" color={CORR_STRENGTH_BADGE[f.strength] || 'gray'} style={{ textTransform: 'capitalize' }}>
                                {f.strength}
                              </Badge>
                            </Table.Td>
                            <Table.Td fz="xs" visibleFrom="sm">{f.reasoning}</Table.Td>
                            <Table.Td c="dimmed" fz="xs" fs="italic" visibleFrom="sm">{f.caveat}</Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Box>
                ) : (
                  <Text size="sm" c="dimmed">No significant anatomically-relevant correlations found in this window.</Text>
                )}
              </>
            )}
          </>
        ) : null}
      </Paper>

      {weeksMode === 'block' && (
        <Paper withBorder p="md">
          <Group justify="space-between" mb="sm">
            <Group gap="xs">
              <Trophy size={18} />
              <Text fw={500}>Program Evaluation</Text>
              {evalReport && (
                <Badge color={evalReport.cached ? 'blue' : 'green'} variant="light" size="sm">
                  {evalReport.cached ? `Cached ${evalReport.generated_at ? new Date(evalReport.generated_at).toLocaleDateString() : ''}` : 'Just generated'}
                </Badge>
              )}
              {evalReport?.stance && (
                <Badge color={STANCE_COLORS[evalReport.stance] || 'gray'} variant="light" size="sm" style={{ textTransform: 'capitalize' }}>
                  {evalReport.stance}
                </Badge>
              )}
            </Group>
            <Button
              variant="subtle"
              size="xs"
              onClick={refreshEvaluation}
              disabled={evalLoading || completedCount < 4}
              leftSection={<RefreshCw size={14} style={evalLoading ? { animation: 'spin 1s linear infinite' } : undefined} />}
            >
              Regenerate
            </Button>
          </Group>

          {completedCount < 4 ? (
            <Text size="sm" c="dimmed">Program evaluation requires at least 4 completed sessions in the current block. Complete more sessions and return here.</Text>
          ) : evalLoading ? (
            <Group gap="xs" py="md">
              <Loader size="xs" />
              <Text size="sm" c="dimmed">Evaluating your training block with AI sports scientist...</Text>
            </Group>
          ) : evalError ? (
            <Text size="sm" c="red">{evalError}</Text>
          ) : evalReport ? (
            <>
              {evalReport.insufficient_data ? (
                <Text size="sm" c="dimmed">{evalReport.insufficient_data_reason || 'Insufficient data for program evaluation.'}</Text>
              ) : (
                <Stack gap="md">
                  {evalReport.summary && (
                    <Text size="sm" c="dimmed" p="sm" fs="italic" style={{ background: 'var(--mantine-color-default-hover)', borderRadius: 'var(--mantine-radius-sm)' }}>{evalReport.summary}</Text>
                  )}

                  {evalReport.competition_alignment.length > 0 && (
                    <Stack gap="xs">
                      <Text size="sm" fw={500}>Competition Alignment</Text>
                      <Stack gap="xs">
                        {evalReport.competition_alignment.map((ca, i) => (
                          <Group key={i} gap="sm" align="flex-start" p="xs" style={{ background: 'var(--mantine-color-default-hover)', borderRadius: 'var(--mantine-radius-sm)' }}>
                            <Badge color={ALIGN_COLORS[ca.alignment] || 'gray'} variant="light" size="sm" style={{ textTransform: 'capitalize', marginTop: 2 }}>{ca.alignment}</Badge>
                            <Stack gap={2}>
                              <Text size="sm" fw={500}>{ca.competition} <Text span size="xs" c="dimmed">({ca.role}{typeof ca.weeks_to_comp === 'number' ? `, ${ca.weeks_to_comp.toFixed(1)} wks out` : ''})</Text></Text>
                              <Text size="xs" c="dimmed">{ca.reason}</Text>
                            </Stack>
                          </Group>
                        ))}
                      </Stack>
                    </Stack>
                  )}

                  <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                    {evalReport.what_is_working.length > 0 && (
                      <Stack gap="xs">
                        <Text size="sm" fw={500} c="green">What's Working</Text>
                        <Stack gap={4}>
                          {evalReport.what_is_working.map((item, i) => (
                            <Group key={i} gap="xs" align="flex-start" wrap="nowrap">
                              <Badge variant="light" color="green" size="sm">✓</Badge>
                              <Text size="xs">{item}</Text>
                            </Group>
                          ))}
                        </Stack>
                      </Stack>
                    )}
                    {evalReport.what_is_not_working.length > 0 && (
                      <Stack gap="xs">
                        <Text size="sm" fw={500} c="red">Needs Attention</Text>
                        <Stack gap={4}>
                          {evalReport.what_is_not_working.map((item, i) => (
                            <Group key={i} gap="xs" align="flex-start" wrap="nowrap">
                              <Badge variant="light" color="red" size="sm">✗</Badge>
                              <Text size="xs">{item}</Text>
                            </Group>
                          ))}
                        </Stack>
                      </Stack>
                    )}
                  </SimpleGrid>

                  {evalReport.small_changes.length > 0 && (
                    <Stack gap="xs">
                      <Text size="sm" fw={500}>Suggested Adjustments</Text>
                      <Stack gap="xs">
                        {evalReport.small_changes.map((sc, i) => (
                          <Paper key={i} withBorder p="sm">
                            <Group gap="xs" mb={4}>
                              <Badge color={PRIORITY_COLORS[sc.priority] || 'gray'} variant="light" size="sm" style={{ textTransform: 'capitalize' }}>{sc.priority}</Badge>
                              <Text size="sm" fw={500}>{sc.change}</Text>
                            </Group>
                            <Text size="xs" c="dimmed">{sc.why}</Text>
                            {sc.risk && <Text size="xs" c="orange" mt={4}>Risk: {sc.risk}</Text>}
                          </Paper>
                        ))}
                      </Stack>
                    </Stack>
                  )}

                  {evalReport.monitoring_focus.length > 0 && (
                    <Stack gap="xs">
                      <Text size="sm" fw={500}>Monitor Closely</Text>
                      <Group gap="xs" wrap="wrap">
                        {evalReport.monitoring_focus.map((item, i) => (
                          <Badge key={i} color="blue" variant="light">{item}</Badge>
                        ))}
                      </Group>
                    </Stack>
                  )}

                  {evalReport.conclusion && (
                    <Text size="sm" fw={500} pt="sm" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>{evalReport.conclusion}</Text>
                  )}
                </Stack>
              )}
            </>
          ) : null}
        </Paper>
      )}
    </>
  );
}
