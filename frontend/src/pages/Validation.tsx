import { useState, useEffect, useMemo } from 'react';
import KPICard from '../components/KPICard';
import QualityScoreGauge from '../charts/QualityScoreGauge';
import SeverityPieChart from '../charts/SeverityPieChart';
import StageBarChart from '../charts/StageBarChart';
import FindingsAccordion from '../components/FindingsAccordion';
import ReturnsDistributionChart from '../charts/ReturnsDistributionChart';
import CandlestickChart from '../charts/CandlestickChart';
import { calculateSMA, calculateEMA, calculateRSI, calculateMACD, type OHLCData } from '../charts/technicalIndicators';
import { getDemoMetadata, runValidation, getChart_data } from '../services/api';
import { DemoMetadata, ValidationResponse } from '../types';

const Validation: React.FC = () => {
  const [selectedSource, setSelectedSource] = useState<'demo' | 'upload'>('demo');
  const [demoData, setDemoData] = useState<DemoMetadata | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [chartData, setChartData] = useState<OHLCData[]>([]);
  const [anomalies, setAnomalies] = useState<{index: number, score: number}[]>([]);
  const [loadingChart, setLoadingChart] = useState(false);

  useEffect(() => {
    loadDemoData();
  }, []);

  useEffect(() => {
    if (selectedSource === 'demo' && demoData) {
      loadChartData(demoData.name);
    }
  }, [selectedSource, demoData]);

  const loadDemoData = async () => {
    try {
      setLoadingData(true);
      const data = await getDemoMetadata();
      setDemoData(data);
    } catch (error) {
      console.error('Failed to load demo data:', error);
    } finally {
      setLoadingData(false);
    }
  };

  const loadChartData = async (datasetName?: string) => {
    try {
      setLoadingChart(true);
      const data = await getChart_data(datasetName);
      if (data.success && data.data) {
        setChartData(data.data);
        // Extract anomalies from validation report if available
        if (validationResult?.report) {
          const anomalyStage = validationResult.report.stage_results.find(s => s.stage_name === 'Anomaly Detection');
          if (anomalyStage) {
            const anomalyIndices = anomalyStage.findings
              .filter(f => f.context && typeof f.context === 'object' && f.context.index !== undefined)
              .map(f => ({
                index: f.context.index as number,
                score: f.context.score as number || 0.5
              }));
            setAnomalies(anomalyIndices);
          }
        }
      }
    } catch (error) {
      console.error('Failed to load chart data:', error);
    } finally {
      setLoadingChart(false);
    }
  };

  const handleRunValidation = async () => {
    setIsRunning(true);
    try {
      let path: string | undefined;
      let name: string | undefined;

      if (selectedSource === 'demo' && demoData) {
        path = undefined;
        name = 'INFY.NS (Infosys) 2024';
      } else if (uploadFile) {
        path = '/api/datasets/upload';
        name = uploadFile.name;
      }

      const response = await runValidation(path, name);
      if (response.success) {
        setValidationResult(response);
        // Load chart data with anomalies from the new validation
        await loadChartData(name);
      }
    } catch (error) {
      console.error('Failed to run validation:', error);
    } finally {
      setIsRunning(false);
    }
  };

  const downloadReport = async (type: 'json' | 'csv' | 'txt') => {
    if (!validationResult?.run_id) return;

    try {
      let response;
      if (type === 'json') response = await fetch(`/api/reports/${validationResult.run_id}/json`);
      else if (type === 'csv') response = await fetch(`/api/reports/${validationResult.run_id}/csv`);
      else response = await fetch(`/api/reports/${validationResult.run_id}/txt`);

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `quantsentinel_${validationResult.dataset_name}.${type}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to download report:', error);
    }
  };

  const calculateReturns = () => {
    if (!demoData?.preview) return [];
    // Simulate returns - in real app, we'd calculate from actual Close prices
    return [];
  };

  // Calculate technical indicators from chart data
  const sma20 = useMemo(() => calculateSMA(chartData, 20), [chartData]);
  const sma50 = useMemo(() => calculateSMA(chartData, 50), [chartData]);
  const ema20 = useMemo(() => calculateEMA(chartData, 20), [chartData]);
  const rsi14 = useMemo(() => calculateRSI(chartData, 14), [chartData]);
  const macd = useMemo(() => calculateMACD(chartData), [chartData]);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setUploadFile(file);
      setValidationResult(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Data Validation</h2>
          <p className="text-slate-400">Run quality checks on financial market data</p>
        </div>
      </div>

      {/* Dataset Selection */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">Select Dataset</h3>

        <div className="flex space-x-4 mb-4">
          <button
            onClick={() => setSelectedSource('demo')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              selectedSource === 'demo'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            Demo Dataset (INFY.NS 2024)
          </button>
          <button
            onClick={() => setSelectedSource('upload')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              selectedSource === 'upload'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            Upload CSV File
          </button>
        </div>

        {selectedSource === 'demo' ? (
          <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
            {loadingData ? (
              <div className="text-slate-400">Loading demo data...</div>
            ) : demoData ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-slate-400">Dataset</div>
                  <div className="font-medium text-white">{demoData.name}</div>
                </div>
                <div>
                  <div className="text-sm text-slate-400">Records</div>
                  <div className="font-medium text-white">{demoData.records.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-sm text-slate-400">Date Range</div>
                  <div className="font-medium text-white">
                    {demoData.date_range.start} to {demoData.date_range.end}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-slate-400">Columns</div>
                  <div className="font-medium text-white">{demoData.columns.join(', ')}</div>
                </div>
              </div>
            ) : (
              <div className="text-slate-400">Could not load demo data</div>
            )}
          </div>
        ) : (
          <div className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center">
            <input
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <div className="text-slate-400 mb-2">
                <svg className="w-12 h-12 mx-auto mb-2 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <span className="text-blue-400 hover:text-blue-300 font-medium">Click to upload CSV file</span>
              <p className="text-sm text-slate-500 mt-2">or drag and drop CSV here</p>
              <p className="text-xs text-slate-600 mt-1">Expected columns: Date, Open, High, Low, Close, Volume</p>
            </label>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={handleRunValidation}
            disabled={isRunning}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white rounded-lg font-medium transition-colors"
          >
            {isRunning ? 'Running Validation...' : '▶ Run Validation'}
          </button>
        </div>
      </div>

      {/* Results */}
      {validationResult && (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div
            className={`p-4 rounded-lg border ${
              validationResult.assessment.overall_status === 'PASS'
                ? 'bg-green-900/20 border-green-800'
                : validationResult.assessment.overall_status === 'WARNING'
                ? 'bg-amber-900/20 border-amber-800'
                : 'bg-red-900/20 border-red-800'
            }`}
          >
            <div className="flex items-center space-x-3">
              <span className={`text-2xl ${
                validationResult.assessment.overall_status === 'PASS'
                  ? 'text-green-400'
                  : validationResult.assessment.overall_status === 'WARNING'
                  ? 'text-amber-400'
                  : 'text-red-400'
              }`}>
                {validationResult.assessment.overall_status === 'PASS' ? '✓' : validationResult.assessment.overall_status === 'WARNING' ? '⚠' : '✕'}
              </span>
              <div>
                <div className="text-lg font-bold text-white">
                  {validationResult.assessment.overall_status} - Quality Score: {validationResult.assessment.score}/100
                </div>
                <div className="text-slate-400 text-sm">{validationResult.assessment.summary}</div>
              </div>
            </div>
          </div>

          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <KPICard label="Quality Score" value={`${validationResult.assessment.score}/100`} />
            <KPICard label="Total Findings" value={validationResult.assessment.status_counts.total} />
            <KPICard label="FAIL" value={validationResult.assessment.status_counts.fail_count} />
            <KPICard label="WARNING" value={validationResult.assessment.status_counts.warning_count} />
            <KPICard label="PASS" value={validationResult.assessment.status_counts.pass_count} />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
              <h3 className="text-lg font-semibold text-white mb-4">Quality Score</h3>
              <QualityScoreGauge score={validationResult.assessment.score} />
            </div>
            <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
              <h3 className="text-lg font-semibold text-white mb-4">Severity Distribution</h3>
              <SeverityPieChart
                failCount={validationResult.assessment.status_counts.fail_count}
                warningCount={validationResult.assessment.status_counts.warning_count}
                passCount={validationResult.assessment.status_counts.pass_count}
              />
            </div>
            <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
              <h3 className="text-lg font-semibold text-white mb-4">Stage-wise Findings</h3>
              <StageBarChart
                stages={(validationResult.report?.stage_results || []).map(stage => ({
                  stage: stage.stage_name,
                  pass: (stage.findings || []).filter(f => f.status === 'PASS').length,
                  warning: (stage.findings || []).filter(f => f.status === 'WARNING').length,
                  fail: (stage.findings || []).filter(f => f.status === 'FAIL').length,
                }))}
              />
            </div>
          </div>

          {/* Candlestick Chart with Technical Indicators */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Price Chart with Technical Indicators</h3>
              <div className="flex space-x-4 text-xs">
                <div className="flex items-center"><div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div><span className="text-slate-400">SMA 20</span></div>
                <div className="flex items-center"><div className="w-3 h-3 bg-purple-500 rounded-full mr-2"></div><span className="text-slate-400">SMA 50</span></div>
                <div className="flex items-center"><div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div><span className="text-slate-400">EMA 20</span></div>
                <div className="flex items-center"><div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div><span className="text-slate-400">RSI 14</span></div>
                <div className="flex items-center"><div className="w-3 h-3 bg-orange-500 rounded-full mr-2"></div><span className="text-slate-400">MACD</span></div>
              </div>
            </div>
            {loadingChart ? (
              <div className="flex items-center justify-center h-96 text-slate-400">Loading chart data...</div>
            ) : chartData.length > 0 ? (
              <CandlestickChart data={chartData} anomalies={anomalies} height={500} />
            ) : (
              <div className="flex items-center justify-center h-96 text-slate-400">No chart data available. Run validation to see chart with anomalies.</div>
            )}
          </div>

          {/* Technical Indicators Details */}
          {chartData.length > 0 && (
            <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
              <h3 className="text-lg font-semibold text-white mb-4">Technical Indicators at a Glance</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div className="text-sm text-slate-400">SMA 20 (20-day)</div>
                  <div className="text-xl font-bold text-blue-400">
                    {sma20.length > 0 ? sma20[sma20.length - 1].toFixed(2) : '-'}
                  </div>
                </div>
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div className="text-sm text-slate-400">SMA 50 (50-day)</div>
                  <div className="text-xl font-bold text-purple-400">
                    {sma50.length > 0 ? sma50[sma50.length - 1].toFixed(2) : '-'}
                  </div>
                </div>
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div className="text-sm text-slate-400">EMA 20 (20-day)</div>
                  <div className="text-xl font-bold text-green-400">
                    {ema20.length > 0 ? ema20[ema20.length - 1].toFixed(2) : '-'}
                  </div>
                </div>
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div className="text-sm text-slate-400">RSI 14 (14-day)</div>
                  <div className="text-xl font-bold text-yellow-400">
                    {rsi14.length > 0 ? rsi14[rsi14.length - 1].toFixed(2) : '-'}
                  </div>
                </div>
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div className="text-sm text-slate-400">MACD Line</div>
                  <div className="text-xl font-bold text-orange-400">
                    {macd.length > 0 ? macd[macd.length - 1].macd.toFixed(2) : '-'}
                  </div>
                </div>
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div className="text-sm text-slate-400">Signal Line</div>
                  <div className="text-xl font-bold text-red-400">
                    {macd.length > 0 ? macd[macd.length - 1].signal.toFixed(2) : '-'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Returns Distribution */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
            <h3 className="text-lg font-semibold text-white mb-4">Returns Distribution</h3>
            <ReturnsDistributionChart returns={calculateReturns()} />
          </div>

          {/* Findings */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
            <h3 className="text-lg font-semibold text-white mb-4">Validation Findings</h3>
            <FindingsAccordion stages={validationResult.report.stage_results} />
          </div>

          {/* Downloads */}
          <div className="flex space-x-4">
            <button
              onClick={() => downloadReport('json')}
              className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
            >
              Download JSON Report
            </button>
            <button
              onClick={() => downloadReport('csv')}
              className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
            >
              Download CSV Findings
            </button>
            <button
              onClick={() => downloadReport('txt')}
              className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
            >
              Download Text Summary
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Validation;
