import { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';

interface ReturnsData {
  return: number;
  frequency: number;
  normal: number;
}

interface ReturnsDistributionChartProps {
  returns: number[];
}

const ReturnsDistributionChart: React.FC<ReturnsDistributionChartProps> = ({ returns }) => {
  const chartData = useMemo(() => {
    if (returns.length === 0) return [];

    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const std = Math.sqrt(
      returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length
    );

    const min = Math.min(...returns);
    const max = Math.max(...returns);
    const binCount = 50;
    const binWidth = (max - min) / binCount;

    const bins: Record<number, number> = {};
    for (let i = 0; i < binCount; i++) {
      bins[i] = 0;
    }

    returns.forEach((r) => {
      const binIndex = Math.min(Math.floor((r - min) / binWidth), binCount - 1);
      bins[binIndex]++;
    });

    const data: ReturnsData[] = [];
    for (let i = 0; i < binCount; i++) {
      const x = min + (i + 0.5) * binWidth;
      const normal = (returns.length * binWidth) * (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mean) / std, 2));
      data.push({
        return: x,
        frequency: bins[i],
        normal: normal,
      });
    }

    return data;
  }, [returns]);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="return"
            stroke="#94a3b8"
            fontSize={11}
            tickFormatter={(value) => `${value.toFixed(1)}%`}
          />
          <YAxis stroke="#94a3b8" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#f1f5f9',
            }}
            formatter={(value: number) => value.toFixed(2)}
          />
          <Bar dataKey="frequency" name="Observed" fill="#3b82f6" opacity={0.7} />
          <Line type="monotone" dataKey="normal" name="Normal" stroke="#ef4444" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ReturnsDistributionChart;
