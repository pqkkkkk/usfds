export interface ConfusionMatrix {
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface ThresholdPoint {
  threshold: number;
  precision: number;
  recall: number;
  f1_score: number;
  f2_score: number;
  accuracy: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
}

export interface RecommendedThresholds {
  best_f1?: ThresholdPoint;
  best_f2?: ThresholdPoint;
  youden_j?: ThresholdPoint;
  high_recall_90?: ThresholdPoint;
  high_recall_95?: ThresholdPoint;
  [key: string]: ThresholdPoint | undefined;
}

export interface ROCCurve {
  fpr: number[];
  tpr: number[];
  thresholds?: number[];
}

export interface PRCurve {
  precision: number[];
  recall: number[];
  thresholds?: number[];
}

export interface ScoreDistribution {
  bin_edges: number[];
  legit_counts: number[];
  fraud_counts: number[];
}

export interface MetricsData {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  f2_score: number;
  confusion_matrix: ConfusionMatrix;
  roc_auc: number | null;
  pr_auc: number | null;
  threshold_tuning_grid: ThresholdPoint[];
  recommended_thresholds: RecommendedThresholds;
  roc_curve: ROCCurve | null;
  pr_curve: PRCurve | null;
  score_distribution: ScoreDistribution | null;
  model_id?: string;
  run_id?: string;
}

export type PresetKey = 'best_f1' | 'best_f2' | 'youden_j' | 'high_recall_90' | 'high_recall_95' | 'default';

export interface PresetInfo {
  key: PresetKey;
  label: string;
  shortDesc: string;
  icon: string;
  badgeColor: string;
}
