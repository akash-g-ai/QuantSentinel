import { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

interface StageData {
  stage: string;
  pass: number;
  warning: number;
  fail: number;
}

interface StageBarChartProps {
  stages: StageData[];
}

const StageBarChart: React.FC<StageBarChartProps> = ({ stages }) => {
  const data = useMemo(() => {
    return stages.map(stage => ({
      stage: stage.stage,
      pass: stage.pass,
      warning: stage.warning,
      fail: stage.fail,
    }));
  }, [stages]);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="stage"
            angle={-45}
            textAnchor="end"
            height={60}
            stroke="#94a3b8"
            fontSize={11}
          />
          <YAxis stroke="#94a3b8" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#f1f5f9',
            }}
          />
          <Legend verticalAlign="bottom" height={36} wrapperStyle={{ color: '#94a3b8' }} />
          <Bar dataKey="pass" name="PASS" stackId="a" fill="#22c55e" />
          <Bar dataKey="warning" name="WARNING" stackId="a" fill="#f59e0b" />
          <Bar dataKey="fail" name="FAIL" stackId="a" fill="#ef4444" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default StageBarChart;
