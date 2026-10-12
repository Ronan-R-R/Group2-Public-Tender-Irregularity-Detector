import { useMemo } from "react";
import { TenderCard } from "../components/TenderCard";
import { Bar, ErrorBlock, LoadingBlock, PageTitle, Stat } from "../components/ui";
import { useIndex } from "../data/useIndex";
import { overview, topBuyersByFlags } from "../lib/aggregate";
import { SHORT_LABEL } from "../lib/explain";
import { count, date, percent, randShort } from "../lib/format";
import { Link, href, usePageFocus } from "../router";

export function Overview() {
  const state = useIndex();
  usePageFocus(`overview:${state.status}`);

  const derived = useMemo(() => {
    if (state.status !== "ready") return null;
    const rows = state.index.awards;
    return {
      stats: overview(state.index),
      buyers: topBuyersByFlags(rows, 6),
      top: rows.slice(0, 4),
    };
  }, [state]);

  return (
    <>
      <PageTitle eyebrow={state.status === "ready" ? `eTenders awards · data built ${date(state.index.generated_at)}` : "eTenders awards"}>
        Procurement risk overview
      </PageTitle>

      {state.status === "loading" && <LoadingBlock label="Loading tender data" lines={5} />}
      {state.status === "error" && <ErrorBlock message={state.message} onRetry={state.retry} />}
      {state.status === "ready" && derived && (
        <div className="space-y-10">
          <p className="max-w-3xl rounded-md border-l-4 border-l-[var(--sev-high)] bg-surface p-4 text-sm">
            Company and director rules (R1-R6, R9) are switched off until CIPC data is linked, so scores currently top out at{" "}
            {derived.stats.topScore}. Treat every score as a prompt to look closer, not a finding. Award values are shown as
            published but never added up: the feed contains capture errors, including awards that appear to be recorded in
            cents.
          </p>

          <section aria-labelledby="totals">
            <h2 id="totals" className="sr-only">Totals</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat
                label="Awards scored"
                value={count(derived.stats.awards)}
                note={`${count(derived.stats.withValue)} publish a value; median ${randShort(derived.stats.medianValue)}`}
              />
              <Stat
                label="Awards with red flags"
                tone="risk"
                value={count(derived.stats.flagged)}
                note={`${percent(derived.stats.flagged / Math.max(1, derived.stats.awards))} of all awards`}
              />
              <Stat
                label="Price outliers"
                tone="risk"
                value={count(derived.stats.priceOutliers)}
                note="Far above or below comparable awards (R10, R11)"
              />
              <Stat
                label="Non-competitive awards"
                value={count(derived.stats.nonCompetitive)}
                note={`${percent(derived.stats.nonCompetitive / Math.max(1, derived.stats.nonCompetitiveEvaluated))} single-source, deviation or limited`}
              />
            </div>
          </section>

          <section aria-labelledby="by-flag">
            <h2 id="by-flag" className="mb-3 text-2xl">Explore by red flag</h2>
            <ul className="flex flex-wrap gap-2">
              <li>
                <Link to={href.tenders({ flagged: "1" })} className="btn btn-primary no-underline">
                  All red flags <span className="font-mono">{count(derived.stats.flagged)}</span>
                </Link>
              </li>
              {state.index.rules
                .filter((r) => (state.index.summary.fired[r.id] ?? 0) > 0)
                .map((r) => (
                  <li key={r.id}>
                    <Link to={href.tenders({ rule: r.id })} className="btn btn-ghost no-underline" title={r.title}>
                      {SHORT_LABEL[r.id] ?? r.title}
                      <span className="font-mono text-muted">{count(state.index.summary.fired[r.id] ?? 0)}</span>
                    </Link>
                  </li>
                ))}
            </ul>
          </section>

          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <section aria-labelledby="buyers">
              <h2 id="buyers" className="text-2xl">Buyers with the most flagged awards</h2>
              <p className="mb-3 text-sm text-muted">Awards from each buyer that carry at least one red flag.</p>
              <ol className="card divide-y divide-line">
                {derived.buyers.map((b) => (
                  <li key={b.id} className="p-4">
                    <div className="flex items-baseline justify-between gap-3">
                      <Link to={href.buyer(b.id)} className="font-semibold text-ink-strong underline decoration-line underline-offset-4 hover:decoration-ink-strong">
                        {b.name}
                      </Link>
                      <span className="shrink-0 font-mono text-sm text-ink-strong">{count(b.flagged)} flagged</span>
                    </div>
                    <div className="mt-2">
                      <Bar
                        fraction={b.flagged / Math.max(1, derived.buyers[0]?.flagged ?? 1)}
                        tone="risk"
                        label={`${b.flagged} flagged awards`}
                      />
                    </div>
                    <p className="mt-1.5 text-sm text-muted">
                      {percent(b.flagged / b.awards)} of {count(b.awards)} awards · highest score {b.maxScore}
                    </p>
                  </li>
                ))}
              </ol>
            </section>

            <section aria-labelledby="top">
              <div className="flex items-baseline justify-between gap-3">
                <h2 id="top" className="text-2xl">Highest-scoring awards</h2>
                <Link to={href.tenders()} className="text-sm font-semibold underline underline-offset-4">
                  See all {count(derived.stats.awards)}
                </Link>
              </div>
              <p className="mb-3 text-sm text-muted">Ranked by risk score, then award value.</p>
              <div className="space-y-3">
                {derived.top.map((a) => (
                  <TenderCard key={a.id} award={a} rules={state.rules} />
                ))}
              </div>
            </section>
          </div>

          <section aria-labelledby="report" className="card p-5">
            <h2 id="report" className="text-xl">Know something about a tender?</h2>
            <p className="mt-1 max-w-3xl text-sm">
              This site does not collect tips. If you have information about procurement corruption, use an organisation that
              can protect you:{" "}
              <a className="underline" href="https://www.corruptionwatch.org.za/" rel="noopener noreferrer">
                Corruption Watch
              </a>{" "}
              or{" "}
              <a className="underline" href="https://amabhungane.org/" rel="noopener noreferrer">
                amaBhungane
              </a>
              .
            </p>
          </section>
        </div>
      )}
    </>
  );
}
