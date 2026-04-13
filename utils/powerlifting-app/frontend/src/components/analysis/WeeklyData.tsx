import { Fragment, useState } from 'react';
import { Paper, Text, Box, Table, Group, Button, Badge, SimpleGrid, Stack } from '@mantine/core';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, BarChart, Bar, CartesianGrid, XAxis, YAxis } from 'recharts';
import type { WeeklyAnalysis } from '@/api/analytics';

const CHART_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1',
];

function rpeTrendIcon(trend?: string) {
  if (!trend) return null;
  if (trend === 'up') return <Text span size="xs" fw={500} c="red">&#9650; rising</Text>;
  if (trend === 'down') return <Text span size="xs" fw={500} c="green">&#9660; improving</Text>;
  return <Text span size="xs" fw={500} c="dimmed">&#9644; stable</Text>;
}

interface WeeklyDataProps {
  data: WeeklyAnalysis;
  viewMode: 'raw' | 'graph';
  perLiftDetails: Record<string, { frequency: number; raw_sets: number; accessories: { name: string; sets: number; volume: number }[] }>;
  muscleGroupSets: Record<string, number>;
  muscleGroupAvgWeekly: { sets: Record<string, number>; volume: Record<string, number> };
}

export function WeeklyData({ data, viewMode, perLiftDetails, muscleGroupSets, muscleGroupAvgWeekly }: WeeklyDataProps) {
  const [expandedLifts, setExpandedLifts] = useState<Set<string>>(new Set());

  return (
    <>
      {/* Per-lift breakdown */}
      {Object.keys(data.lifts).length > 0 && (
        <Paper withBorder p="md">
          <Text fw={500} mb="sm">Per-Lift Breakdown</Text>
          <Box style={{ overflowX: 'auto' }}>
            <Table fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Exercise</Table.Th>
                  <Table.Th ta="right">Freq</Table.Th>
                  <Table.Th ta="right">Sets</Table.Th>
                  <Table.Th ta="right">Progression</Table.Th>
                  <Table.Th ta="right" visibleFrom="sm">R&sup2;</Table.Th>
                  <Table.Th ta="right" visibleFrom="sm">Volume %</Table.Th>
                  <Table.Th ta="right" visibleFrom="sm">Intensity %</Table.Th>
                  <Table.Th ta="right" visibleFrom="sm">Failed</Table.Th>
                  <Table.Th ta="right" visibleFrom="sm">RPE Trend</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {Object.entries(data.lifts).map(([name, lift]) => {
                  const liftKey = name.toLowerCase().replace(' press', '');
                  const details = perLiftDetails[liftKey];
                  const isExpanded = expandedLifts.has(name);
                  return (
                    <Fragment key={name}>
                      <Table.Tr>
                        <Table.Td fw={500}>
                          <Group gap="xs">
                            {name}
                            {details && details.accessories.length > 0 && (
                              <Button
                                variant="subtle"
                                size="compact-xs"
                                color="gray"
                                onClick={() => setExpandedLifts(prev => {
                                  const next = new Set(prev);
                                  if (next.has(name)) next.delete(name); else next.add(name);
                                  return next;
                                })}
                              >
                                {isExpanded ? '▼' : '▶'} {details.accessories.length} acc
                              </Button>
                            )}
                          </Group>
                        </Table.Td>
                        <Table.Td ta="right">{details ? <Text span fz="sm">{details.frequency}/wk</Text> : <Text span fz="sm" c="dimmed">--</Text>}</Table.Td>
                        <Table.Td ta="right">{details ? <Text span fz="sm">{details.raw_sets}</Text> : <Text span fz="sm" c="dimmed">--</Text>}</Table.Td>
                        <Table.Td ta="right">
                          {lift.progression_rate_kg_per_week !== undefined && lift.progression_rate_kg_per_week !== null
                            ? <Text span fz="sm" c={lift.progression_rate_kg_per_week >= 0 ? 'green' : 'red'}>{lift.progression_rate_kg_per_week >= 0 ? '+' : ''}{lift.progression_rate_kg_per_week.toFixed(1)} kg/wk</Text>
                            : <Text span fz="sm" c="dimmed">--</Text>}
                        </Table.Td>
                        <Table.Td ta="right" visibleFrom="sm">
                          {lift.r2 !== undefined && lift.r2 !== null
                            ? <Text span fz="sm" c="dimmed">{(lift.r2 * 100).toFixed(0)}%</Text>
                            : <Text span fz="sm" c="dimmed">--</Text>}
                        </Table.Td>
                        <Table.Td ta="right" visibleFrom="sm">
                          {lift.volume_change_pct !== undefined
                            ? <Text span fz="sm" c={lift.volume_change_pct >= 0 ? 'green' : 'red'}>{lift.volume_change_pct >= 0 ? '+' : ''}{lift.volume_change_pct.toFixed(0)}%</Text>
                            : <Text span fz="sm" c="dimmed">--</Text>}
                        </Table.Td>
                        <Table.Td ta="right" visibleFrom="sm">
                          {lift.intensity_change_pct !== undefined
                            ? <Text span fz="sm" c={lift.intensity_change_pct >= 0 ? 'green' : 'red'}>{lift.intensity_change_pct >= 0 ? '+' : ''}{lift.intensity_change_pct.toFixed(0)}%</Text>
                            : <Text span fz="sm" c="dimmed">--</Text>}
                        </Table.Td>
                        <Table.Td ta="right" visibleFrom="sm">
                          {lift.failed_sets !== undefined && lift.failed_sets > 0
                            ? <Badge variant="light" color="red" size="sm">{lift.failed_sets}</Badge>
                            : <Text span fz="sm" c="dimmed">0</Text>}
                        </Table.Td>
                        <Table.Td ta="right" visibleFrom="sm">{rpeTrendIcon(lift.rpe_trend) || <Text span fz="sm" c="dimmed">--</Text>}</Table.Td>
                      </Table.Tr>
                      {isExpanded && details && details.accessories.length > 0 && (
                        <Table.Tr>
                          <Table.Td colSpan={9}>
                            <Box ml="md">
                              <Text fz="xs" c="dimmed" mb="xs">Accessory / Secondary Work</Text>
                              <SimpleGrid cols={{ base: 2, md: 3, lg: 4 }}>
                                {details.accessories.map(a => (
                                  <Box key={a.name} p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default)' }}>
                                    <Text fz="xs" fw={500}>{a.name}</Text>
                                    <Text fz="xs" c="dimmed">{a.sets} sets · {Math.round(a.volume).toLocaleString()} kg</Text>
                                  </Box>
                                ))}
                              </SimpleGrid>
                            </Box>
                          </Table.Td>
                        </Table.Tr>
                      )}
                    </Fragment>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Box>
        </Paper>
      )}

      {/* Exercise Stats */}
      {data.exercise_stats && Object.keys(data.exercise_stats).length > 0 && (
        <Paper withBorder p="md">
          <Text fw={500} mb="sm">Exercise Volume</Text>
          {viewMode === 'raw' ? (
            <Box style={{ overflowX: 'auto' }}>
              <Table fz="sm">
                <Table.Thead><Table.Tr><Table.Th>Exercise</Table.Th><Table.Th ta="right">Total Sets</Table.Th><Table.Th ta="right">Volume (kg)</Table.Th><Table.Th ta="right">Max (kg)</Table.Th></Table.Tr></Table.Thead>
                <Table.Tbody>
                  {Object.entries(data.exercise_stats)
                    .sort((a, b) => b[1].total_volume - a[1].total_volume)
                    .map(([name, s]) => (
                      <Table.Tr key={name}>
                        <Table.Td fw={500}>{name}</Table.Td>
                        <Table.Td ta="right">{s.total_sets}</Table.Td>
                        <Table.Td ta="right">{s.total_volume.toLocaleString()}</Table.Td>
                        <Table.Td ta="right">{s.max_kg.toFixed(1)}</Table.Td>
                      </Table.Tr>
                    ))}
                </Table.Tbody>
              </Table>
            </Box>
          ) : (
            <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
              <Box>
                <Text fz="xs" c="dimmed" ta="center" mb="xs">Sets Distribution</Text>
                <ResponsiveContainer width="100%" height={350}>
                  <PieChart>
                    <Pie data={Object.entries(data.exercise_stats).sort((a, b) => b[1].total_sets - a[1].total_sets).slice(0, 10).map(([name, s], i) => ({ name, value: s.total_sets, fill: CHART_COLORS[i % CHART_COLORS.length] }))} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                      {Object.entries(data.exercise_stats).sort((a, b) => b[1].total_sets - a[1].total_sets).slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
              <Box>
                <Text fz="xs" c="dimmed" ta="center" mb="xs">Volume Distribution</Text>
                <ResponsiveContainer width="100%" height={350}>
                  <PieChart>
                    <Pie data={Object.entries(data.exercise_stats).sort((a, b) => b[1].total_volume - a[1].total_volume).slice(0, 10).map(([name, s], i) => ({ name, value: s.total_volume, fill: CHART_COLORS[i % CHART_COLORS.length] }))} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                      {Object.entries(data.exercise_stats).sort((a, b) => b[1].total_volume - a[1].total_volume).slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
              <Box>
                <Text fz="xs" c="dimmed" ta="center" mb="xs">Max Weight (kg)</Text>
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={Object.entries(data.exercise_stats).sort((a, b) => b[1].max_kg - a[1].max_kg).slice(0, 10).map(([name, s], i) => ({ name, max_kg: s.max_kg, fill: CHART_COLORS[i % CHART_COLORS.length] }))} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" /><YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="max_kg" radius={[0, 4, 4, 0]}>
                      {Object.entries(data.exercise_stats).sort((a, b) => b[1].max_kg - a[1].max_kg).slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </SimpleGrid>
          )}
        </Paper>
      )}

      {/* Muscle Group Sets */}
      {Object.keys(muscleGroupSets).length > 0 && (
        <Paper withBorder p="md">
          <Text fw={500} mb="sm">Sets by Muscle Group</Text>
          {viewMode === 'raw' ? (
            <SimpleGrid cols={{ base: 2, md: 4, lg: 5 }}>
              {Object.entries(muscleGroupSets).sort((a, b) => b[1] - a[1]).map(([muscle, sets]) => (
                <Stack key={muscle} gap={2} ta="center" p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                  <Text fz="xs" c="dimmed" tt="capitalize">{muscle.replace(/_/g, ' ')}</Text>
                  <Text fz="lg" fw={700}>{Math.round(sets)}</Text>
                </Stack>
              ))}
            </SimpleGrid>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={Object.entries(muscleGroupSets).sort((a, b) => b[1] - a[1]).map(([name, value], i) => ({ name: name.replace(/_/g, ' '), value, fill: CHART_COLORS[i % CHART_COLORS.length] }))} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                  {Object.entries(muscleGroupSets).sort((a, b) => b[1] - a[1]).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Paper>
      )}

      {/* Avg Weekly by Muscle Group */}
      {Object.keys(muscleGroupAvgWeekly.sets).length > 0 && (
        <Paper withBorder p="md">
          <Text fw={500} mb="sm">Avg Weekly by Muscle Group</Text>
          {viewMode === 'raw' ? (
            <Box style={{ overflowX: 'auto' }}>
              <Table fz="sm">
                <Table.Thead><Table.Tr><Table.Th>Muscle Group</Table.Th><Table.Th ta="right">Avg Sets/wk</Table.Th><Table.Th ta="right">Avg Vol/wk (kg)</Table.Th></Table.Tr></Table.Thead>
                <Table.Tbody>
                  {Object.entries(muscleGroupAvgWeekly.sets).sort((a, b) => (muscleGroupAvgWeekly.volume[b[0]] || 0) - (muscleGroupAvgWeekly.volume[a[0]] || 0)).map(([muscle, sets]) => (
                    <Table.Tr key={muscle}>
                      <Table.Td fw={500}>{muscle.replace(/_/g, ' ')}</Table.Td>
                      <Table.Td ta="right">{sets}</Table.Td>
                      <Table.Td ta="right">{(muscleGroupAvgWeekly.volume[muscle] || 0).toLocaleString()}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Box>
          ) : (
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
              <Box>
                <Text fz="xs" c="dimmed" ta="center" mb="xs">Avg Sets/wk</Text>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={Object.entries(muscleGroupAvgWeekly.sets).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name: name.replace(/_/g, ' '), 'Avg Sets/wk': value }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                    <YAxis /><Tooltip />
                    <Bar dataKey="Avg Sets/wk" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
              <Box>
                <Text fz="xs" c="dimmed" ta="center" mb="xs">Avg Vol/wk (kg)</Text>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={Object.entries(muscleGroupAvgWeekly.volume).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name: name.replace(/_/g, ' '), 'Avg Vol/wk': value }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                    <YAxis /><Tooltip />
                    <Bar dataKey="Avg Vol/wk" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </SimpleGrid>
          )}
        </Paper>
      )}
    </>
  );
}
