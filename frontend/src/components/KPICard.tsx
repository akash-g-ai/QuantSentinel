

interface KPICardProps {
  label: string;
  value: string | number;
  subtext?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
}

const KPICard: React.FC<KPICardProps> = ({ label, value, subtext, trend, trendValue }) => {
  const trendColors = {
    up: 'text-green-400',
    down: 'text-red-400',
    neutral: 'text-slate-400',
  };

  return (
    <div className="bg-slate-800 rounded-lg p-5 border border-slate-700 shadow-lg">
      <div className="text-sm text-slate-400 font-medium mb-2">{label}</div>
      <div className="text-3xl font-bold text-white mb-1">{value}</div>
      <div className="flex items-center space-x-2">
        {subtext && <span className="text-sm text-slate-500">{subtext}</span>}
        {trend && trendValue && (
          <span className={`text-sm font-medium ${trendColors[trend]}`}>
            {trendValue}
          </span>
        )}
      </div>
    </div>
  );
};

export default KPICard;
