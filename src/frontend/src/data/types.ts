// Shapes of the public JSON written by src/detection/export.py (schema 1).

export type Severity = "critical" | "high" | "medium" | "low";
export type Level = "none" | "flag" | "alert";
export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

export type MatchStatus =
  | "exact"
  | "strong_fuzzy"
  | "needs_review"
  | "no_match";

export interface RuleInfo {
  id: string;
  title: string;
  severity: Severity;
  points: number;
}


export interface AwardRow {
  id: string;
  ocid: string;
  title: string;
  buyer_id: string;
  buyer: string;
  supplier_id: string;
  supplier: string;
  category: string | null;
  close_date: string | null;
  value: string | null;
  score: number;
  level: Level;
  fired: string[];
  coverage: number;
  needs_review: boolean;
  /** Isolation Forest percentile, 0-100; null when the award has no usable price. */
  anomaly_pct: number | null;
  shard: string;
}

export interface Index {
  schema_version: 1;
  generated_at: string;
  source: { name?: string; url?: string; licence?: string; releases?: number; awards?: number; skipped?: number };
  thresholds: { flag: number; alert: number; max: number };
  rules: RuleInfo[];
  summary: {
    awards: number;
    by_level: Partial<Record<Level, number>>;
    fired: Record<string, number>;
    not_evaluated: Record<string, number>;
  };
  awards: AwardRow[];
}

export interface SupplierMatch {
  status: MatchStatus;
  confidence: number;
  matched_company_name: string | null;
  source: string;
}

export interface RuleOutcome {
  rule_id: string;
  title: string;
  severity: Severity;
  fired: boolean;
  evaluated: boolean;
  points: number;
  needs_review: boolean;
  evidence: Record<string, Json>;
}

export interface AnomalyDetail {
  percentile: number;
  category_median: string;
  buyer_median: string;
  log_vs_category: number;
  log_vs_buyer: number;
}

export interface AwardDetail {
  id: string;
  score: number;
  uncapped_score: number;
  level: Level;
  coverage: number;
  breakdown: RuleOutcome[];
  anomaly: AnomalyDetail | null;

  supplier_match?: SupplierMatch | null;
}

export interface Comparable {
  tender_id: string;
  buyer_name: string | null;
  close_date: string | null;
  award_value: string;
}
