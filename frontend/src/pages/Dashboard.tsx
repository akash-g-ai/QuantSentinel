import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import KPICard from '../components/KPICard';
import QualityScoreGauge from '../charts/QualityScoreGauge';
import SeverityPieChart from '../charts/SeverityPieChart';
import StageBarChart from '../charts/StageBarChart';
import FindingsAccordion from '../components/FindingsAccordion';
import { getValidationHistory } from '../services/api';

interface DashboardProps {
  initialRun?: {
    assessment: {
      score: number;
      overall_status: string;
      status_counts: {
        total: number;
        fail_count: number;
        warning_count: number;
        pass_count: number;
      };
    };
    report: {
      stage_results: Array<{
        stage_name: string;
        status: string;
        findings: Array<{
          rule_id: string;
          status: string;
          message: string;
          affected_rows?: number[];
        }>;
      }>;
    };
  };
}

const Dashboard: React.FC<DashboardProps> = ({ initialRun }) => {
  const [latestRun, setLatestRun] = useState<DashboardProps['initialRun']>(initialRun);
  const navigate = useNavigate();

  useEffect(() => {
    if (!initialRun) {
      loadLatestRun();
    }
  }, [initialRun]);

  const loadLatestRun = async () => {
    try {
      const response = await getValidationHistory();
      if (response.success && response.runs.length > 0) {
        setLatestRun({
          assessment: {
            score: response.runs[0].quality_score,
            overall_status: response.runs[0].overall_status,
            status_counts: {
              total: response.runs[0].total_findings,
              fail_count: response.runs[0].fail_count,
              warning_count: response.runs[0].warning_count,
              pass_count: response.runs[0].pass_count,
            },
          },
          report: {
            stage_results: [],
          },
        });
      }
    } catch (error) {
      console.error('Failed to load latest run:', error);
    }
  };



  if (!latestRun) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">No validation data available. Run a validation to see results.</p>
      </div>
    );
  }

  const { assessment, report } = latestRun;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Dashboard</h2>
          <p className="text-slate-400">Overview of data quality assessments</p>
        </div>
        <button
          onClick={() => navigate('/validation')}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
        >
          Run Validation
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Quality Score"
          value={`${assessment.score}/100`}
          subtext={assessment.overall_status}
        />
        <KPICard
          label="Total Findings"
          value={assessment.status_counts.total}
        />
        <KPICard
          label="Pass"
          value={assessment.status_counts.pass_count}
        />
        <KPICard
          label="Fail"
          value={assessment.status_counts.fail_count}
          trend={assessment.status_counts.fail_count > 0 ? 'neutral' : 'up'}
          trendValue={assessment.status_counts.fail_count === 0 ? '✓ All clear' : ''}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quality Score Gauge */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
          <h3 className="text-lg font-semibold text-white mb-4">Quality Score</h3>
          <QualityScoreGauge score={assessment.score} />
        </div>

        {/* Severity Distribution */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
          <h3 className="text-lg font-semibold text-white mb-4">Severity Distribution</h3>
          <SeverityPieChart
            failCount={assessment.status_counts.fail_count}
            warningCount={assessment.status_counts.warning_count}
            passCount={assessment.status_counts.pass_count}
          />
        </div>

        {/* Stage-wise Findings */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
          <h3 className="text-lg font-semibold text-white mb-4">Stage-wise Findings</h3>
          <StageBarChart
            stages={report.stage_results.map(stage => ({
              stage: stage.stage_name,
              pass: stage.findings.filter(f => f.status === 'PASS').length,
              warning: stage.findings.filter(f => f.status === 'WARNING').length,
              fail: stage.findings.filter(f => f.status === 'FAIL').length,
            }))}
          />
        </div>
      </div>

      {/* Findings */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">Findings Summary</h3>
        <FindingsAccordion stages={report.stage_results} />
      </div>

      {/* Recent History */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">Recent History</h3>
        <div className="text-sm text-slate-400">
          Use the History page to view previous validation runs.
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
