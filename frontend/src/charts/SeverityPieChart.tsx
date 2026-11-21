import { useMemo } from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

interface SeverityPieChartProps {
  failCount: number;
  warningCount: number;
  passCount: number;
}

const SeverityPieChart: React.FC<SeverityPieChartProps> = ({ failCount, warningCount, passCount }) => {
  const data = useMemo(() => {
    const result = [];
    if (passCount > 0) result.push({ name: 'PASS', value: passCount, color: '#22c55e' });
    if (warningCount > 0) result.push({ name: 'WARNING', value: warningCount, color: '#f59e0b' });
    if (failCount > 0) result.push({ name: 'FAIL', value: failCount, color: '#ef4444' });
    if (result.length === 0) result.push({ name: 'PASS', value: 1, color: '#22c55e' });
    return result;
  }, [failCount, warningCount, passCount]);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            innerRadius={60}
            outerRadius={80}
            paddingAngle={5}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Legend
            iconType="circle"
            layout="horizontal"
            verticalAlign="bottom"
            align="center"
            wrapperStyle={{ color: '#94a3b8', fontSize: 12 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SeverityPieChart;
