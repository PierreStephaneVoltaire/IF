import { TargetAllocation } from '@finance-portal/types';
import { formatPercent } from '../utils/formatters';

interface AllocationChartProps {
  allocation: TargetAllocation[];
  title?: string;
}

export function AllocationChart({ allocation, title = 'Asset Allocation' }: AllocationChartProps) {
  if (allocation.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-700 mb-4">{title}</h3>
        <p className="text-gray-500 text-center py-4">No allocation data</p>
      </div>
    );
  }

  const colors = [
    '#3B82F6', // blue
    '#10B981', // green
    '#F59E0B', // amber
    '#EF4444', // red
    '#8B5CF6', // purple
    '#EC4899', // pink
    '#06B6D4', // cyan
    '#F97316', // orange
  ];

  const radius = 80;
  const innerRadius = 50;
  const circumference = 2 * Math.PI * radius;

  let currentAngle = -90; // Start from top

  const segments = allocation.map((item, index) => {
    const angle = (item.current_pct / 100) * 360;
    const startAngle = currentAngle;
    currentAngle += angle;

    return {
      ...item,
      color: colors[index % colors.length],
      startAngle,
      angle,
    };
  });

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-semibold text-gray-700 mb-4">{title}</h3>

      <div className="flex items-center gap-6">
        {/* Donut chart */}
        <svg width="200" height="200" viewBox="0 0 200 200">
          {segments.map((segment, index) => {
            const startRad = (segment.startAngle * Math.PI) / 180;
            const angleRad = (segment.angle * Math.PI) / 180;
            const endRad = startRad + angleRad;

            const x1 = 100 + radius * Math.cos(startRad);
            const y1 = 100 + radius * Math.sin(startRad);
            const x2 = 100 + radius * Math.cos(endRad);
            const y2 = 100 + radius * Math.sin(endRad);

            const largeArc = segment.angle > 180 ? 1 : 0;

            const pathD = `
              M ${100 + innerRadius * Math.cos(startRad)} ${100 + innerRadius * Math.sin(startRad)}
              L ${x1} ${y1}
              A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}
              L ${100 + innerRadius * Math.cos(endRad)} ${100 + innerRadius * Math.sin(endRad)}
              A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${100 + innerRadius * Math.cos(startRad)} ${100 + innerRadius * Math.sin(startRad)}
              Z
            `;

            return (
              <path
                key={index}
                d={pathD}
                fill={segment.color}
                className="hover:opacity-80 transition-opacity"
              />
            );
          })}
          {/* Center text */}
          <text x="100" y="95" textAnchor="middle" className="text-sm fill-gray-600">
            Total
          </text>
          <text x="100" y="115" textAnchor="middle" className="text-lg font-bold fill-gray-800">
            100%
          </text>
        </svg>

        {/* Legend */}
        <div className="flex-1 space-y-2">
          {segments.map((segment, index) => (
            <div key={index} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded"
                  style={{ backgroundColor: segment.color }}
                />
                <span className="text-gray-700">{segment.category}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-medium">{formatPercent(segment.current_pct)}</span>
                <span className="text-gray-400 text-xs">
                  target: {formatPercent(segment.target_pct)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default AllocationChart;
