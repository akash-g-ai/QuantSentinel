import { useMemo } from 'react';

interface OHLCData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export function calculateSMA(data: OHLCData[], period: number): (number | null)[] {
  // Handle empty data
  if (!data || data.length === 0) {
    return [];
  }
  
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      const slice = data.slice(i - period + 1, i + 1);
      const sum = slice.reduce((acc, d) => acc + d.close, 0);
      result.push(sum / period);
    }
  }
  return result;
}

export function calculateEMA(data: OHLCData[], period: number): (number | null)[] {
  // Handle empty data or insufficient data
  if (!data || data.length === 0 || data.length < period) {
    return new Array(data?.length || 0).fill(null);
  }
  
  const result: (number | null)[] = new Array(data.length).fill(null);
  const k = 2 / (period + 1);
  
  // Use SMA for first value
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i].close;
  }
  result[period - 1] = sum / period;
  
  // Calculate EMA for remaining values
  for (let i = period; i < data.length; i++) {
    result[i] = data[i].close * k + result[i - 1]! * (1 - k);
  }
  
  return result;
}

export function calculateRSI(data: OHLCData[], period: number = 14): (number | null)[] {
  // Handle empty data
  if (!data || data.length === 0) {
    return [];
  }
  
  const result: (number | null)[] = new Array(data.length).fill(null);
  
  if (data.length <= period) return result;
  
  // Calculate price changes
  const changes: number[] = [0];
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i].close - data[i - 1].close);
  }
  
  // Calculate initial average gain/loss
  let avgGain = 0;
  let avgLoss = 0;
  
  for (let i = 1; i <= period; i++) {
    if (changes[i] > 0) {
      avgGain += changes[i];
    } else {
      avgLoss -= changes[i];
    }
  }
  
  avgGain /= period;
  avgLoss /= period;
  
  // RSI for period-th index
  result[period] = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss));
  
  // Calculate subsequent RSI values
  for (let i = period + 1; i < data.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    
    result[i] = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss));
  }
  
  return result;
}

export function calculateMACD(data: OHLCData[]): { macd: number; signal: number; histogram: number }[] {
  // Handle empty data
  if (!data || data.length === 0) {
    return [];
  }
  
  const ema12 = calculateEMA(data, 12);
  const ema26 = calculateEMA(data, 26);
  
  const macdLine: number[] = [];
  for (let i = 0; i < data.length; i++) {
    macdLine.push((ema12[i] || 0) - (ema26[i] || 0));
  }
  
  // Signal line is EMA of MACD line
  const signalLine: (number | null)[] = new Array(data.length).fill(null);
  const k = 2 / (9 + 1);
  
  // Find first valid MACD value
  let firstValid = -1;
  for (let i = 0; i < data.length; i++) {
    if (macdLine[i] !== 0) {
      firstValid = i;
      break;
    }
  }
  
  if (firstValid >= 8) {
    // Use simple average for initial signal
    let sum = 0;
    for (let i = firstValid - 8; i <= firstValid; i++) {
      sum += macdLine[i];
    }
    signalLine[firstValid] = sum / 9;
    
    // Calculate subsequent signal values
    for (let i = firstValid + 1; i < data.length; i++) {
      signalLine[i] = macdLine[i] * k + signalLine[i - 1]! * (1 - k);
    }
  }
  
  // Histogram
  const histogram: number[] = [];
  for (let i = 0; i < data.length; i++) {
    histogram.push(macdLine[i] - (signalLine[i] || 0));
  }
  
  return macdLine.map((macd, i) => ({
    macd,
    signal: signalLine[i] || 0,
    histogram: histogram[i],
  }));
}
