import type { AnomalyDetail, Json, RuleOutcome } from "../data/types";
import { count, date, rand, signedPercent } from "./format";

/** Short chip labels. Factual, never accusatory. */
export const SHORT_LABEL: Record<string, string> = {
  R1: "Registered < 90 days",
  R2: "Registered < 30 days",
  R3: "Dormant before award",
  R4: "Shared directors",
  R5: "Director overlap with bidders",
  R6: "PEP match",
  R7: "Repeat winner",
  R8: "Non-competitive",
  R9: "Sector mismatch",
  R10: "Price far above peers",
  R11: "Price far below peers",
  R12: "Round value",
};

const str = (v: Json | undefined): string => (v === null || v === undefined ? "" : String(v));
const n = (v: Json | undefined): number => (typeof v === "number" ? v : Number(v));

/** One plain sentence saying what the rule found, built from its evidence. */
export function explain(r: RuleOutcome): string {
  const e = r.evidence;
  if (!r.evaluated) return `Not evaluated: ${str(e["reason"]) || "data not available"}.`;

  switch (r.rule_id) {
    case "R1":
    case "R2": {
      const days = n(e["days_registered_before_close"]);
      if (e["registered_after_close"] === true) {
        return `The company's registration date (${date(str(e["registration_date"]))}) is after the tender closed. Either it did not exist when bids closed, or the CIPC record matched the wrong company.`;
      }
      return `Registered ${count(days)} days before the tender closed (${date(str(e["registration_date"]))}).`;
    }
    case "R3":
      return e["last_annual_return"]
        ? `Last CIPC annual return before the award was filed ${count(n(e["days_since_last_annual_return"]))} days before the tender closed.`
        : `No CIPC annual return on record before the award; registered ${date(str(e["registration_date"]))}.`;
    case "R4": {
      const companies = n(e["company_count"]);
      if (r.fired) {
        return `A director of this supplier also sits on ${count(companies - 1)} other companies that won from ${str(e["buyer_name"])} between ${date(str(e["window_start"]))} and ${date(str(e["window_end"]))}.`;
      }
      return n(e["directors_checked"]) === 0
        ? "No directors are on record for this supplier."
        : `Its directors link at most ${count(companies)} winning ${companies === 1 ? "company" : "companies"} at this buyer in 12 months; the rule needs 3.`;
    }
    case "R5": {
      const overlapping = Array.isArray(e["overlapping_bidders"]) ? e["overlapping_bidders"].length : 0;
      if (r.fired) {
        return `Shares a director with ${count(overlapping)} losing ${overlapping === 1 ? "bidder" : "bidders"} on this tender.`;
      }
      return n(e["losing_bidders"]) === 0
        ? "No other bidders are recorded for this tender."
        : `No director is shared with the ${count(n(e["bidders_checked"]))} losing bidders that could be checked.`;
    }
    case "R6": {
      const matched = n(e["matched_directors"]);
      return r.fired
        ? `${count(matched)} ${matched === 1 ? "director matches" : "directors match"} a politically exposed persons list. A name match is not proof of identity, and being politically exposed is not wrongdoing; a person must check it.`
        : `None of the ${count(n(e["directors_checked"]))} directors match a politically exposed persons list.`;
    }
    case "R7":
      return `${count(n(e["award_count"]))} contracts from ${str(e["buyer_name"])} between ${date(str(e["window_start"]))} and ${date(str(e["window_end"]))}, counting this one.`;
    case "R8": {
      const basis = Array.isArray(e["basis"]) ? e["basis"].map(String) : [];
      const method = str(e["procurement_method"]) || "not published";
      if (!r.fired) return `Procurement method: ${method}.`;
      return basis.includes("non-open procedure")
        ? `Awarded through a non-open procedure: ${method}.`
        : `Only one tenderer was recorded.`;
    }
    case "R9":
      return `Company industry "${str(e["company_industry"])}" against tender category "${str(e["tender_category"])}".`;
    case "R10":
    case "R11":
      return `${rand(str(e["award_value"]))} is ${signedPercent(n(e["percent_vs_median"]))} against the median of ${count(n(e["comparable_count"]))} comparable "${str(e["category"])}" awards (${rand(str(e["comparable_median"]))}) in the previous 24 months.`;
    case "R12":
      return r.fired
        ? `The award value is an exact multiple of ${rand(n(e["multiple_of"]))}.`
        : "The award value is not a round number.";
    default:
      return r.fired ? "This rule fired." : "This rule did not fire.";
  }
}

/** "4.2 times", "a tenth of": how far a price sits from a typical one. */
export function ratioPhrase(log10Ratio: number): string {
  const ratio = 10 ** log10Ratio;
  if (ratio >= 1.05) return `${ratio >= 10 ? Math.round(ratio).toLocaleString("en-ZA") : ratio.toFixed(1)} times`;
  if (ratio <= 0.95) {
    const inverse = 1 / ratio;
    return `1/${inverse >= 10 ? Math.round(inverse).toLocaleString("en-ZA") : inverse.toFixed(1)} of`;
  }
  return "about the same as";
}

/** Values 100 times or more from their category's typical price are more often capture errors than prices. */
export function looksLikeCaptureError(a: AnomalyDetail): boolean {
  return Math.abs(a.log_vs_category) >= 2;
}
