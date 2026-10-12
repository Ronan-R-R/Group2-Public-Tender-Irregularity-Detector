import type { AwardDetail, AwardRow, Index } from "../data/types";

// Synthetic awards. Names are fictional; shapes match the export.
export function row(overrides: Partial<AwardRow> = {}): AwardRow {
  return {
    id: "ocds-9t57fa-1/1",
    ocid: "ocds-9t57fa-1",
    title: "Supply of fictional laboratory consumables",
    buyer_id: "etenders:1",
    buyer: "Fictional Department of Health",
    supplier_id: "etenders:100",
    supplier: "Fictional Medical Supplies",
    category: "Supplies: Medical",
    close_date: "2025-03-14",
    value: "1000000",
    score: 0,
    level: "none",
    fired: [],
    coverage: 0.5,
    needs_review: false,
    shard: "ab",
    ...overrides,
  };
}

export function index(awards: AwardRow[]): Index {
  const fired: Record<string, number> = {};
  for (const a of awards) for (const r of a.fired) fired[r] = (fired[r] ?? 0) + 1;
  return {
    schema_version: 1,
    generated_at: "2026-10-12T09:00:00+00:00",
    source: { name: "test", releases: awards.length, awards: awards.length, skipped: 0 },
    thresholds: { flag: 50, alert: 75, max: 100 },
    rules: [
      { id: "R7", title: "Repeat winner: 5+ awards from the same buyer in 24 months", severity: "medium", points: 8 },
      { id: "R8", title: "Non-competitive award", severity: "medium", points: 8 },
      { id: "R10", title: "Award value far above comparable awards", severity: "high", points: 15 },
      { id: "R12", title: "Award value is a suspiciously round number", severity: "low", points: 3 },
    ],
    summary: { awards: awards.length, by_level: { none: awards.length }, fired, not_evaluated: { R8: 0 } },
    awards,
  };
}

export function detail(overrides: Partial<AwardDetail> = {}): AwardDetail {
  return { id: "ocds-9t57fa-1/1", score: 0, uncapped_score: 0, level: "none", coverage: 0.5, breakdown: [], ...overrides };
}
