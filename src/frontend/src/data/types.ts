// Shapes of the public JSON written by src/detection/export.py (schema 1).

export type Severity = "critical" | "high" | "medium" | "low";
export type Level = "none" | "flag" | "alert";
export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

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

export interface AwardDetail {
  id: string;
  score: number;
  uncapped_score: number;
  level: Level;
  coverage: number;
  breakdown: RuleOutcome[];
}

export interface Comparable {
  tender_id: string;
  buyer_name: string | null;
  close_date: string | null;
  award_value: string;
}
