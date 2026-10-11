/**
 * Detection Jobs and Alert Investigation types
 */

export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type InvestigationStatus = 'NEW' | 'UNDER_REVIEW' | 'CONFIRMED_FRAUD' | 'FALSE_POSITIVE' | 'DISMISSED';

export interface DetectionJob {
  id: string;
  projectId: string;
  name: string;
  type: 'BATCH' | 'STREAM';
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  totalTransactions: number;
  flaggedCount: number;
  runtimeSeconds?: number;
  createdAt: string;
}

export interface FraudAlert {
  id: string;
  transactionId: string;
  timestamp: string;
  amount: number;
  currency: string;
  cardBin?: string;
  merchantCategory?: string;
  riskScore: number;
  severity: AlertSeverity;
  triggeredRules: string[];
  mlModelScore: number;
  status: InvestigationStatus;
  assignee?: string;
}
