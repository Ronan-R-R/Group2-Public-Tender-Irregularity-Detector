import { describe, expect, it } from "vitest";
import type { RuleOutcome } from "../data/types";
import { parse } from "../router";
import { index, row } from "../test/fixtures";
import { buyers, filterAwards, median, overview, suppliersOf, topBuyersByFlags } from "./aggregate";
import { explain } from "./explain";
import { date, percent, rand, randShort, signedPercent, toNumber } from "./format";

describe("format", () => {
  it("formats rand values and marks missing ones", () => {
    expect(rand("142500000")).toMatch(/^R\s?142[\s ]500[\s ]000$/);
    expect(rand(null)).toBe("Not published");
    expect(rand("not a number")).toBe("Not published");
  });

  it("shortens large values", () => {
    expect(randShort(142_500_000)).toBe("R143m");
    expect(randShort(14_900_000)).toBe("R14.9m");
    expect(randShort(2_300_000_000)).toBe("R2.3bn");
    expect(randShort(null)).toBe("Not published");
  });

  it("signs percentages", () => {
    expect(signedPercent(92.54)).toBe("+92.5%");
    expect(signedPercent(-40)).toBe("-40%");
    expect(signedPercent(0)).toBe("0%");
    expect(signedPercent(176399.6)).toMatch(/^\+176[\s ]399\.6%$/);
  });

  it("formats shares with a decimal point", () => {
    expect(percent(0.148)).toBe("14.8%");
    expect(percent(0.5)).toBe("50%");
  });

  it("parses numbers defensively", () => {
    expect(toNumber("1.5")).toBe(1.5);
    expect(toNumber("")).toBeNull();
    expect(toNumber("NaN")).toBeNull();
  });

  it("formats ISO dates without timezone drift", () => {
    expect(date("2025-03-14")).toMatch(/14 Mar 2025/);
    expect(date(null)).toBe("Not published");
  });
});

describe("aggregate", () => {
  const rows = [
    row({ id: "a", fired: ["R10"], value: "5000000", score: 15 }),
    row({ id: "b", fired: [], value: "1000000" }),
    row({ id: "c", fired: ["R8"], value: null, buyer_id: "etenders:2", buyer: "Fictional Municipality", supplier_id: "etenders:200", supplier: "Other Trading" }),
    row({ id: "d", fired: ["R8", "R12"], value: "3000000", buyer_id: "etenders:2", buyer: "Fictional Municipality", score: 11 }),
  ];

  it("summarises with counts and medians, never value sums", () => {
    const o = overview(index(rows));
    expect(o).toMatchObject({ awards: 4, withValue: 3, medianValue: 3_000_000, flagged: 3, nonCompetitive: 2, priceOutliers: 1, topScore: 15 });
    expect(o).not.toHaveProperty("totalValue");
  });

  it("computes medians for odd, even and empty sets", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 3, 2])).toBe(2.5);
    expect(median([])).toBeNull();
  });

  it("groups buyers and ranks them by flagged awards", () => {
    const all = buyers(rows);
    expect(all).toHaveLength(2);
    expect(topBuyersByFlags(rows, 5).map((b) => [b.name, b.flagged])).toEqual([
      ["Fictional Municipality", 2],
      ["Fictional Department of Health", 1],
    ]);
  });

  it("lists a buyer's most frequent suppliers", () => {
    const s = suppliersOf(rows, "etenders:2", 5);
    expect(s.map((x) => [x.id, x.awards, x.flagged])).toEqual([
      ["etenders:100", 1, 1],
      ["etenders:200", 1, 1],
    ]);
  });

  it("filters by search words, rules, score and buyer", () => {
    const base = { q: "", rules: [], minScore: 0, sort: "score" as const };
    expect(filterAwards(rows, { ...base, q: "other trading" }).map((a) => a.id)).toEqual(["c"]);
    expect(filterAwards(rows, { ...base, rules: ["R12", "R10"] }).map((a) => a.id)).toEqual(["a", "d"]);
    expect(filterAwards(rows, { ...base, minScore: 11 }).map((a) => a.id)).toEqual(["a", "d"]);
    expect(filterAwards(rows, { ...base, buyerId: "etenders:2" }).map((a) => a.id)).toEqual(["c", "d"]);
    expect(filterAwards(rows, { ...base, sort: "value" }).map((a) => a.id)).toEqual(["a", "d", "b", "c"]);
  });
});

describe("explain", () => {
  const outcome = (o: Partial<RuleOutcome>): RuleOutcome => ({
    rule_id: "R10", title: "t", severity: "high", fired: true, evaluated: true, points: 15, needs_review: false, evidence: {}, ...o,
  });

  it("explains price outliers against the median", () => {
    const text = explain(outcome({ evidence: { award_value: "2500000", percent_vs_median: 150, comparable_count: 12, category: "Supplies: Medical", comparable_median: "1000000.00" } }));
    expect(text).toContain("+150%");
    expect(text).toContain("12 comparable");
  });

  it("explains the registered-after-close case without accusing", () => {
    const text = explain(outcome({ rule_id: "R2", evidence: { registered_after_close: true, registration_date: "2025-04-01", days_registered_before_close: -18 } }));
    expect(text).toMatch(/matched the wrong company/);
  });

  it("states the reason when a rule was not evaluated", () => {
    expect(explain(outcome({ evaluated: false, fired: false, evidence: { reason: "CIPC registration date unknown" } }))).toBe(
      "Not evaluated: CIPC registration date unknown.",
    );
  });
});

describe("router", () => {
  it("parses every route", () => {
    expect(parse("/", "")).toEqual({ name: "overview" });
    expect(parse("/tenders", "?rule=R10").name).toBe("tenders");
    expect(parse("/tenders/ocds-9t57fa-1%2F2", "")).toEqual({ name: "tender", id: "ocds-9t57fa-1/2" });
    expect(parse("/buyers/etenders%3A213", "")).toEqual({ name: "buyer", id: "etenders:213" });
  });

  it("falls back to not-found for unknown or malformed paths", () => {
    expect(parse("/nope/x/y", "").name).toBe("not-found");
    expect(parse("/tenders/%E0%A4%A", "").name).toBe("not-found");
  });
});
