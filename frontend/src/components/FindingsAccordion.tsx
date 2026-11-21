import { ChevronDown, AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';

interface Finding {
  rule_id: string;
  status: string;
  message: string;
  affected_rows?: number[] | string;
}

interface StageResult {
  stage_name: string;
  status: string;
  findings: Finding[];
}

interface FindingsAccordionProps {
  stages: StageResult[];
}

const FindingsAccordion: React.FC<FindingsAccordionProps> = ({ stages }) => {
  const statusColors = {
    PASS: 'text-green-400 border-green-500/30 bg-green-500/10',
    WARNING: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    FAIL: 'text-red-400 border-red-500/30 bg-red-500/10',
  };

  const statusIcons = {
    PASS: CheckCircle,
    WARNING: AlertTriangle,
    FAIL: AlertCircle,
  };

  return (
    <div className="space-y-4">
      {stages.map((stage) => {
        const StageIcon = statusIcons[stage.status as keyof typeof statusIcons] || CheckCircle;
        const stageColor = statusColors[stage.status as keyof typeof statusColors];

        return (
          <div key={stage.stage_name} className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
            <details>
              <summary className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-700/50 transition-colors">
                <div className="flex items-center space-x-3">
                  <StageIcon className={`w-5 h-5 ${stageColor.split(' ')[0]}`} />
                  <span className="font-semibold text-white">{stage.stage_name}</span>
                  <span className={`text-xs px-2 py-1 rounded-full border ${stageColor.split(' ')[2]} ${stageColor.split(' ')[3]}`}>
                    {stage.status}
                  </span>
                  <span className="text-sm text-slate-400">
                    {(stage.findings?.length || 0)} finding{(stage.findings?.length || 0) !== 1 ? 's' : ''}
                  </span>
                </div>
                <ChevronDown className="w-5 h-5 text-slate-400" />
              </summary>
              <div className="px-4 pb-4 border-t border-slate-700">
                {(stage.findings?.length || 0) === 0 ? (
                  <div className="py-4 text-center text-slate-400">No findings</div>
                ) : (
                  <div className="space-y-2">
                    {stage.findings.map((finding, index) => {
                      const FindingIcon = statusIcons[finding.status as keyof typeof statusIcons] || CheckCircle;
                      const findingColor = statusColors[finding.status as keyof typeof statusColors];

                      return (
                        <div
                          key={index}
                          className={`p-3 rounded-lg border ${findingColor.split(' ')[2]} ${findingColor.split(' ')[3]}`}
                        >
                          <div className="flex items-start space-x-3">
                            <FindingIcon className={`w-4 h-4 mt-0.5 ${findingColor.split(' ')[0]}`} />
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-1">
                                <span className="font-medium text-sm">{finding.rule_id}</span>
                                <span className={`text-xs px-2 py-0.5 rounded-full border ${findingColor.split(' ')[2]} ${findingColor.split(' ')[3]}`}>
                                  {finding.status}
                                </span>
                              </div>
                              <p className="text-sm text-slate-300 mb-2">{finding.message}</p>
                              {finding.affected_rows && (Array.isArray(finding.affected_rows) ? finding.affected_rows.length : (finding.affected_rows as string).split(' ').length) > 0 && (
                                <div className="text-xs text-slate-500 font-mono">
                                  {Array.isArray(finding.affected_rows) ? (
                                    <>
                                      Affected rows: {finding.affected_rows.slice(0, 5).join(', ')}
                                      {finding.affected_rows.length > 5 && '...'}
                                    </>
                                  ) : (
                                    <>
                                      Affected rows: {(finding.affected_rows as string).split(' ').slice(0, 5).join(', ')}
                                      {(finding.affected_rows as string).split(' ').length > 5 && '...'}
                                    </>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </details>
          </div>
        );
      })}
    </div>
  );
};

export default FindingsAccordion;
