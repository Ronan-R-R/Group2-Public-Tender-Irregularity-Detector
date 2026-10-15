import type { AwardRow, Index } from "../data/types";
import { toNumber } from "./format";

export const PRICE_RULES = ["R10", "R11"];

export function hasFlags(a: AwardRow): boolean {
  return a.fired.length > 0;
}

function value(a: AwardRow): number {
  return toNumber(a.value) ?? 0;
}

// Award values in the eTenders feed include capture errors: 98 awards exceed
// R10bn and several municipal awards equal the municipality's annual budget,
// consistent with amounts captured in cents. Sums of these values are not
// meaningful, so aggregates use counts and medians only.
export function median(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((x, y) => x - y);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
}

function publishedValues(rows: readonly AwardRow[]): number[] {
  return rows.map((a) => toNumber(a.value)).filter((v): v is number => v !== null && v > 0);
}

export interface Overview {
  awards: number;
  withValue: number;
  medianValue: number | null;
  flagged: number;
  nonCompetitive: number;
  nonCompetitiveEvaluated: number;
  priceOutliers: number;
  topScore: number;
}

export function overview(index: Index): Overview {
  const rows = index.awards;
  const evaluatedR8 = rows.length - (index.summary.not_evaluated["R8"] ?? 0);
  return {
    awards: rows.length,
    withValue: publishedValues(rows).length,
    medianValue: median(publishedValues(rows)),
    flagged: rows.filter(hasFlags).length,
    nonCompetitive: index.summary.fired["R8"] ?? 0,
    nonCompetitiveEvaluated: evaluatedR8,
    priceOutliers: rows.filter((a) => a.fired.some((r) => PRICE_RULES.includes(r))).length,
    topScore: rows.reduce((m, a) => Math.max(m, a.score), 0),
  };
}

export interface BuyerSummary {
  id: string;
  name: string;
  awards: number;
  flagged: number;
  medianValue: number | null;
  maxScore: number;
}

export function buyers(rows: readonly AwardRow[]): BuyerSummary[] {
  const groups = new Map<string, AwardRow[]>();
  for (const a of rows) {
    const g = groups.get(a.buyer_id);
    if (g) g.push(a);
    else groups.set(a.buyer_id, [a]);
  }
  return [...groups.entries()].map(([id, g]) => ({
    id,
    name: g[0]!.buyer,
    awards: g.length,
    flagged: g.filter(hasFlags).length,
    medianValue: median(publishedValues(g)),
    maxScore: g.reduce((m, a) => Math.max(m, a.score), 0),
  }));
}

/** Buyers ranked by how many of their awards carry red flags. */
export function topBuyersByFlags(rows: readonly AwardRow[], limit: number): BuyerSummary[] {
  return buyers(rows)
    .filter((b) => b.flagged > 0)
    .sort((x, y) => y.flagged - x.flagged || y.maxScore - x.maxScore || x.name.localeCompare(y.name))
    .slice(0, limit);
}

export interface SupplierShare {
  id: string;
  name: string;
  awards: number;
  flagged: number;
}

/** Suppliers a buyer awards most often: the raw material for R7 (repeat winner). */
export function suppliersOf(rows: readonly AwardRow[], buyerId: string, limit: number): SupplierShare[] {
  const map = new Map<string, SupplierShare>();
  for (const a of rows) {
    if (a.buyer_id !== buyerId) continue;
    const s = map.get(a.supplier_id) ?? { id: a.supplier_id, name: a.supplier, awards: 0, flagged: 0 };
    s.awards += 1;
    if (hasFlags(a)) s.flagged += 1;
    map.set(a.supplier_id, s);
  }
  return [...map.values()]
    .sort((x, y) => y.awards - x.awards || y.flagged - x.flagged || x.name.localeCompare(y.name))
    .slice(0, limit);
}

export interface ListFilter {
  q: string;
  rules: string[];
  minScore: number;
  buyerId?: string;
  sort: "score" | "value" | "date" | "anomaly";
}

export function filterAwards(rows: readonly AwardRow[], f: ListFilter): AwardRow[] {
  const words = f.q.toLowerCase().split(/\s+/).filter(Boolean);
  const out = rows.filter((a) => {
    if (a.score < f.minScore) return false;
    if (f.buyerId && a.buyer_id !== f.buyerId) return false;
    if (f.rules.length && !f.rules.some((r) => a.fired.includes(r))) return false;
    if (words.length) {
      const hay = `${a.title} ${a.buyer} ${a.supplier} ${a.ocid}`.toLowerCase();
      if (!words.every((w) => hay.includes(w))) return false;
    }
    return true;
  });
  if (f.sort === "value") out.sort((x, y) => value(y) - value(x));
  else if (f.sort === "date") out.sort((x, y) => (y.close_date ?? "").localeCompare(x.close_date ?? ""));
  else if (f.sort === "anomaly") out.sort((x, y) => (y.anomaly_pct ?? -1) - (x.anomaly_pct ?? -1));
  // "score": the export is already ranked by level, score, then value.
  return out;
}
