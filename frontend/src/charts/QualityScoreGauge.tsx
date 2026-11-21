import { useMemo } from 'react';
import { ResponsiveContainer, PolarAngleAxis, PolarGrid, Radar, RadarChart } from 'recharts';

interface QualityScoreGaugeProps {
  score: number;
}

const QualityScoreGauge: React.FC<QualityScoreGaugeProps> = ({ score }) => {
  const color = useMemo(() => {
    if (score >= 70) return '#22c55e';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  }, [score]);

  const data = useMemo(() => [
    {
      subject: 'Quality',
      A: score,
      B: 100,
      fullMark: 100,
    },
  ], [score]);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#94a3b8', fontSize: 14 }}
          />
          <PolarGrid gridType="circle" stroke="#334155" />
          <Radar
            name="Score"
            dataKey="A"
            stroke={color}
            strokeWidth={3}
            fill={color}
            fillOpacity={0.3}
          />
          <Radar
            name="Max"
            dataKey="B"
            stroke="#334155"
            strokeWidth={2}
            fill="transparent"
          />
        </RadarChart>
      </ResponsiveContainer>
      <div className="text-center mt-4">
        <span className="text-4xl font-bold" style={{ color }}>
          {score}
        </span>
        <span className="text-xl text-slate-400 ml-2">/100</span>
      </div>
    </div>
  );
};

export default QualityScoreGauge;
