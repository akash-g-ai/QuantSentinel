// Types for API responses

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
}

export interface DemoDataset {
  name: string;
  path: string;
  size_bytes: number;
  exists: boolean;
}

export interface PriceRange {
  low: number;
  high: number;
  open_start: number;
  close_end: number;
}

export interface VolumeStats {
  mean: number;
  max: number;
  sum: number;
}

export interface DemoMetadata {
  name: string;
  records: number;
  columns: string[];
  date_range: {
    start: string;
    end: string;
  };
  price_range: PriceRange;
  volume_stats: VolumeStats;
  preview: Record<string, unknown>[];
}

export interface UploadResponse {
  success: boolean;
  filename: string;
  path: string;
  size_bytes: number;
  message: string;
}

export interface Assessment {
  score: number;
  overall_status: string;
  summary: string;
  status_counts: StatusCounts;
}

export interface StatusCounts {
  total: number;
  fail_count: number;
  warning_count: number;
  pass_count: number;
}

export interface ValidationResponse {
  success: boolean;
  run_id: string;
  dataset_name: string;
  dataset_path: string;
  assessment: Assessment;
  report: ValidationReport;
  timestamp: string;
}

export interface ValidationReport {
  dataset_name: string;
  stage_results: StageResult[];
}

export interface StageResult {
  stage_name: string;
  status: string;
  finding_count: number;
  findings: Finding[];
}

export interface Finding {
  rule_id: string;
  status: string;
  message: string;
  affected_rows: number[];
  metadata: Record<string, unknown>;
}

export interface RunRecord {
  run_id: string;
  dataset_name: string;
  recorded_at: string;
  quality_score: number;
  overall_status: string;
  total_findings: number;
  fail_count: number;
  warning_count: number;
  pass_count: number;
}

export interface HistoryResponse {
  success: boolean;
  total: number;
  runs: RunRecord[];
}

export interface ValidationResult {
  success: boolean;
  run_id: string;
  dataset_name: string;
  timestamp: string;
  assessment: Assessment;
  stages: StageSummary[];
  findings: FindingSummary[];
}

export interface StageSummary {
  stage_name: string;
  status: string;
  finding_count: number;
}

export interface FindingSummary {
  rule_id: string;
  status: string;
  message: string;
  affected_row_count: number;
}

// Types for chart data
export interface OHLCData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TechnicalIndicator {
  name: string;
  values: number[];
}

// Types for component props
export interface ThemeContextType {
  isDark: boolean;
  toggleTheme: () => void;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
}
