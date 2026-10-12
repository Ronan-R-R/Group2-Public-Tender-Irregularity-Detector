import type { Comparable, Json } from "../data/types";
import { date, rand, randShort, signedPercent, toNumber } from "../lib/format";

interface Row {
  label: string;
  value: number;
  kind: "this" | "median" | "peer";
}

/** "Cross-buyer comparison": this award against recent same-category awards, log scale. */
export function PriceChart({ evidence }: { evidence: Record<string, Json> }) {
  const comparables = (Array.isArray(evidence["comparables"]) ? evidence["comparables"] : []) as unknown as Comparable[];
  const own = toNumber(String(evidence["award_value"] ?? ""));
  const median = toNumber(String(evidence["comparable_median"] ?? ""));
  const rows: Row[] = [];
  if (own) rows.push({ label: "This award", value: own, kind: "this" });
  for (const c of comparables) {
    const v = toNumber(c.award_value);
    if (v && v > 0) rows.push({ label: `${c.buyer_name ?? "Unknown buyer"} · ${date(c.close_date)}`, value: v, kind: "peer" });
  }
  if (rows.length < 2) return null;

  // Values in one category routinely span three orders of magnitude, so a
  // linear axis would flatten every comparable to nothing.
  const logs = rows.map((r) => Math.log10(r.value)).concat(median ? [Math.log10(median)] : []);
  const lo = Math.min(...logs) - 0.15;
  const hi = Math.max(...logs);
  const pos = (v: number) => ((Math.log10(v) - lo) / Math.max(hi - lo, 0.001)) * 100;
  const pct = Number(evidence["percent_vs_median"]);

  return (
    <figure className="card p-4">
      <figcaption className="mb-3">
        <p className="font-semibold text-ink-strong">Award value against comparable awards</p>
        <p className="text-sm text-muted">
          Same category, previous 24 months, {rows.length - 1} most recent shown. Log scale.
          {median ? ` Median ${rand(median)}; this award ${signedPercent(pct)}.` : ""}
        </p>
      </figcaption>
      <ul className="space-y-1.5">
        {rows.map((r, i) => (
          <li key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 sm:grid-cols-[14rem_minmax(0,1fr)_6rem]">
            <span className={`truncate text-sm ${r.kind === "this" ? "font-semibold text-risk" : ""}`} title={r.label}>
              {r.label}
            </span>
            <span className="order-3 col-span-2 sm:order-none sm:col-span-1">
              <span className="relative block h-2.5 rounded-sm bg-sunken" aria-hidden="true">
                <span
                  className={`absolute inset-y-0 left-0 rounded-sm ${r.kind === "this" ? "bg-risk" : "bg-control"}`}
                  style={{ width: `${Math.max(2, pos(r.value)).toFixed(1)}%` }}
                />
                {median ? (
                  <span className="absolute inset-y-[-3px] w-0.5 bg-ink-strong" style={{ left: `${pos(median).toFixed(1)}%` }} />
                ) : null}
              </span>
            </span>
            <span className="text-right font-mono text-sm">{randShort(r.value)}</span>
          </li>
        ))}
      </ul>
      {median ? (
        <p className="mt-3 flex items-center gap-2 text-xs text-muted">
          <span className="inline-block h-3 w-0.5 bg-ink-strong" aria-hidden="true" /> Median of comparable awards
        </p>
      ) : null}
    </figure>
  );
}
