import type { AnomalyDetail } from "../data/types";
import { looksLikeCaptureError, ratioPhrase } from "../lib/explain";
import { count, rand } from "../lib/format";

/** The Isolation Forest signal. Shown beside the risk score, never added to it. */
export function AnomalyPanel({ signal, priced }: { signal: AnomalyDetail | null; priced: number }) {
  return (
    <section aria-labelledby="unusual-price" className="card p-5">
      <h2 id="unusual-price" className="text-2xl">
        Unusual price signal
      </h2>
      <p className="mb-4 text-sm text-muted">
        A machine-learning check (Isolation Forest) that compares this award's value with what its category and its buyer
        usually pay. It sits beside the risk score and does not add to it.
      </p>

      {signal === null ? (
        <p className="text-sm">
          No signal for this award: its value is not published, is below R1 000, or its category is missing.
        </p>
      ) : (
        <>
          <p className="font-semibold text-ink-strong">
            More unusual than {signal.percentile}% of {count(priced)} priced awards.
          </p>
          <div
            className="mt-2 h-2.5 w-full overflow-hidden rounded-sm bg-sunken"
            role="img"
            aria-label={`Percentile ${signal.percentile} of 100`}
          >
            <div
              className={`h-full ${signal.percentile >= 99 ? "bg-risk" : "bg-control"}`}
              style={{ width: `${Math.max(1, signal.percentile)}%` }}
            />
          </div>
          <ul className="mt-3 space-y-1 text-sm">
            <li>
              {ratioPhrase(signal.log_vs_category)} the typical award in its category ({rand(signal.category_median)}).
            </li>
            <li>
              {ratioPhrase(signal.log_vs_buyer)} this buyer's typical award ({rand(signal.buyer_median)}).
            </li>
          </ul>
          {looksLikeCaptureError(signal) ? (
            <p className="mt-3 rounded-md bg-sunken p-3 text-sm">
              This value is at least 100 times away from the typical price for its category. Check the published value for a
              capture error, such as an amount entered in cents or thousands, before reading anything into it.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
