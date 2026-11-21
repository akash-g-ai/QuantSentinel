import { useMemo } from 'react';

interface OHLCData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Anomaly {
  index: number;
  score: number;
}

interface CandlestickChartProps {
  data: OHLCData[];
  anomalies?: Anomaly[];
  height?: number;
}

const CandlestickChart: React.FC<CandlestickChartProps> = ({ data, anomalies = [], height = 500 }) => {
  const chartConfig = useMemo(() => {
    if (data.length === 0) return null;

    const prices = data.flatMap(d => [d.high, d.low]);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const pricePadding = (maxPrice - minPrice) * 0.1;
    const priceMin = minPrice - pricePadding;
    const priceMax = maxPrice + pricePadding;

    const volumes = data.map(d => d.volume);
    const maxVolume = Math.max(...volumes);

    const chartWidth = 1200;
    const chartHeight = height;
    const candleWidth = 8;
    const candleSpacing = 4;
    const volumeHeight = chartHeight * 0.15;
    const priceAreaHeight = chartHeight - volumeHeight;

    const priceScale = (price: number) =>
      priceAreaHeight - ((price - priceMin) / (priceMax - priceMin)) * priceAreaHeight;

    const candleX = (index: number) => index * (candleWidth + candleSpacing) + 50;

    return {
      priceMin,
      priceMax,
      maxVolume,
      chartWidth,
      chartHeight,
      priceAreaHeight,
      volumeHeight,
      candleWidth,
      candleSpacing,
      priceScale,
      candleX,
      candles: data.map((d, i) => ({
        ...d,
        x: candleX(i),
        yOpen: priceScale(d.open),
        yHigh: priceScale(d.high),
        yLow: priceScale(d.low),
        yClose: priceScale(d.close),
        isGreen: d.close >= d.open,
        anomaly: anomalies.find(a => a.index === i),
      })),
    };
  }, [data, anomalies, height]);

  if (!chartConfig) return <div className="flex items-center justify-center h-96 text-slate-400">No data available</div>;

  const { chartWidth, chartHeight, priceAreaHeight, volumeHeight, candleWidth, candles, priceMin, priceMax, maxVolume } = chartConfig;

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden" style={{ width: '100%', height }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet">
        {/* Price Grid */}
        {[0, 0.25, 0.5, 0.75, 1].map(p => {
          const y = p * priceAreaHeight;
          const price = priceMax - p * (priceMax - priceMin);
          return (
            <g key={p}>
              <line x1="50" y1={y} x2={chartWidth} y2={y} stroke="#334155" strokeDasharray="4 4" />
              <text x="0" y={y - 4} fill="#94a3b8" fontSize="10" textAnchor="end">
                {price.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* Volume Grid */}
        {[0, 0.5, 1].map(p => {
          const y = priceAreaHeight + p * volumeHeight;
          const vol = p * maxVolume;
          return (
            <g key={`vol-${p}`}>
              <line x1="50" y1={y} x2={chartWidth} y2={y} stroke="#334155" strokeDasharray="4 4" />
              <text x="0" y={y + 12} fill="#94a3b8" fontSize="10" textAnchor="end">
                {vol >= 1000000 ? `${(vol / 1000000).toFixed(1)}M` : `${(vol / 1000).toFixed(0)}K`}
              </text>
            </g>
          );
        })}

        {/* Volume Bars */}
        {candles.map((candle, i) => {
          const barHeight = (candle.volume / maxVolume) * (volumeHeight - 10);
          const x = candle.x - candleWidth / 2;
          const y = priceAreaHeight + (volumeHeight - barHeight);
          return (
            <rect
              key={`vol-${i}`}
              x={x}
              y={y}
              width={candleWidth}
              height={barHeight}
              fill={candle.isGreen ? '#22c55e' : '#ef4444'}
              opacity={0.4}
            />
          );
        })}

        {/* Candlesticks */}
        {candles.map((candle, i) => {
          const x = candle.x - candleWidth / 2;
          const top = Math.min(candle.yOpen, candle.yClose);
          const height = Math.abs(candle.yOpen - candle.yClose) || 1;

          return (
            <g key={i}>
              {/* Wick */}
              <line
                x1={candle.x}
                y1={candle.yHigh}
                x2={candle.x}
                y2={candle.yLow}
                stroke={candle.isGreen ? '#22c55e' : '#ef4444'}
                strokeWidth={1}
              />
              {/* Body */}
              <rect
                x={x}
                y={top}
                width={candleWidth}
                height={height}
                fill={candle.isGreen ? '#22c55e' : '#ef4444'}
                rx={1}
              />
              {/* Anomaly marker */}
              {candle.anomaly && (
                <circle
                  cx={candle.x}
                  cy={candle.yClose + 15}
                  r={4}
                  fill="#f59e0b"
                  stroke="#1e293b"
                  strokeWidth={2}
                />
              )}
            </g>
          );
        })}

        {/* Anomaly labels */}
        {candles.filter(c => c.anomaly).map((candle, i) => (
          <text
            key={`label-${i}`}
            x={candle.x}
            y={candle.yClose + 28}
            fill="#f59e0b"
            fontSize="10"
            textAnchor="middle"
          >
            📉
          </text>
        ))}
      </svg>
    </div>
  );
};

export default CandlestickChart;
