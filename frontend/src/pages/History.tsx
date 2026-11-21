import { useEffect, useState } from 'react';
import { getValidationHistory, getValidationResult } from '../services/api';
import { RunRecord } from '../types';
import { StatusCounts } from '../types';

interface HistoryRecord extends RunRecord {
  assessment?: {
    status_counts: StatusCounts;
  };
}

const History: React.FC = () => {
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [selectedRun, setSelectedRun] = useState<HistoryRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      setLoading(true);
      const response = await getValidationHistory();
      if (response.success) {
        setHistory(response.runs);
      }
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetails = async (runId: string) => {
    try {
      setRunLoading(true);
      const response = await getValidationResult(runId);
      if (response.success) {
        const run = history.find((r) => r.run_id === runId);
        if (run) {
          setSelectedRun({
            ...run,
            assessment: {
              status_counts: response.assessment.status_counts,
            },
          });
        }
      }
    } catch (error) {
      console.error('Failed to load run details:', error);
    } finally {
      setRunLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      PASS: 'bg-green-500/20 text-green-400 border-green-500/30',
      WARNING: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      FAIL: 'bg-red-500/20 text-red-400 border-red-500/30',
    };
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium border ${colors[status] || ''}`}>
        {status}
      </span>
    );
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PASS': return 'text-green-400';
      case 'WARNING': return 'text-amber-400';
      case 'FAIL': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Validation History</h2>
          <p className="text-slate-400">Previous validation runs recorded in the audit log</p>
        </div>
        <button
          onClick={loadHistory}
          disabled={loading}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 text-white rounded-lg font-medium transition-colors"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* History Table */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-900">
              <tr className="text-left text-sm text-slate-400">
                <th className="px-6 py-4 font-medium">Dataset</th>
                <th className="px-6 py-4 font-medium">Date</th>
                <th className="px-6 py-4 font-medium">Score</th>
                <th className="px-6 py-4 font-medium">Status</th>
                <th className="px-6 py-4 font-medium">Total</th>
                <th className="px-6 py-4 font-medium">Fail</th>
                <th className="px-6 py-4 font-medium">Warning</th>
                <th className="px-6 py-4 font-medium">Pass</th>
                <th className="px-6 py-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {history.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-8 text-center text-slate-400">
                    No validation runs recorded yet. Run a validation first.
                  </td>
                </tr>
              ) : (
                history.map((run) => (
                  <tr key={run.run_id} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-medium text-white">{run.dataset_name}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-slate-400">
                        {new Date(run.recorded_at).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-white">{run.quality_score}</div>
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(run.overall_status)}</td>
                    <td className="px-6 py-4 text-slate-300">{run.total_findings}</td>
                    <td className="px-6 py-4">
                      <span className={getStatusColor(run.overall_status)}>{run.fail_count}</span>
                    </td>
                    <td className="px-6 py-4 text-slate-300">{run.warning_count}</td>
                    <td className="px-6 py-4 text-slate-300">{run.pass_count}</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => loadRunDetails(run.run_id)}
                        disabled={runLoading}
                        className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                      >
                        {runLoading && selectedRun?.run_id === run.run_id ? 'Loading...' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected Run Details */}
      {selectedRun && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
          <h3 className="text-lg font-semibold text-white mb-4">Run Details</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <div className="text-sm text-slate-400">Dataset</div>
              <div className="text-white">{selectedRun.dataset_name}</div>
            </div>
            <div>
              <div className="text-sm text-slate-400">Timestamp</div>
              <div className="text-white">{new Date(selectedRun.recorded_at).toLocaleString()}</div>
            </div>
            <div>
              <div className="text-sm text-slate-400">Quality Score</div>
              <div className="text-white">{selectedRun.quality_score}/100</div>
            </div>
            <div>
              <div className="text-sm text-slate-400">Overall Status</div>
              <div className={getStatusColor(selectedRun.overall_status)}>{selectedRun.overall_status}</div>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-900 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-white">{selectedRun.total_findings}</div>
              <div className="text-xs text-slate-500 mt-1">Total Findings</div>
            </div>
            <div className="bg-slate-900 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-red-400">{selectedRun.fail_count}</div>
              <div className="text-xs text-slate-500 mt-1">Failures</div>
            </div>
            <div className="bg-slate-900 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-amber-400">{selectedRun.warning_count}</div>
              <div className="text-xs text-slate-500 mt-1">Warnings</div>
            </div>
            <div className="bg-slate-900 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-green-400">{selectedRun.pass_count}</div>
              <div className="text-xs text-slate-500 mt-1">Passes</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default History;
