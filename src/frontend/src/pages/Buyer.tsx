import { useMemo, useState } from "react";
import { TenderCard } from "../components/TenderCard";
import { Bar, EmptyBlock, ErrorBlock, LoadingBlock, PageTitle, Stat } from "../components/ui";
import { useIndex } from "../data/useIndex";
import { buyers, suppliersOf } from "../lib/aggregate";
import { count, percent, randShort } from "../lib/format";
import { Link, href, usePageFocus } from "../router";

const PAGE = 20;

export function Buyer({ id }: { id: string }) {
  const state = useIndex();
  usePageFocus(`buyer:${id}:${state.status}`);
  const [shown, setShown] = useState(PAGE);

  const data = useMemo(() => {
    if (state.status !== "ready") return null;
    const rows = state.index.awards.filter((a) => a.buyer_id === id);
    const summary = buyers(rows)[0];
    if (!summary) return null;
    return { rows, summary, suppliers: suppliersOf(rows, id, 8) };
  }, [state, id]);

  if (state.status === "loading") return <LoadingBlock label="Loading buyer" />;
  if (state.status === "error") return <ErrorBlock message={state.message} onRetry={state.retry} />;
  if (!data) {
    return (
      <>
        <PageTitle eyebrow="Buyer">Buyer not found</PageTitle>
        <EmptyBlock title="No awards from this buyer are in the current data.">
          <Link to={href.overview()} className="underline">Back to the overview</Link>
        </EmptyBlock>
      </>
    );
  }

  const { rows, summary, suppliers } = data;
  const topCount = suppliers[0]?.awards ?? 1;

  return (
    <>
      <PageTitle eyebrow="Procuring entity">{summary.name}</PageTitle>

      <div className="space-y-10">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Awards" value={count(summary.awards)} />
          <Stat
            label="With red flags"
            tone="risk"
            value={count(summary.flagged)}
            note={`${percent(summary.flagged / summary.awards)} of this buyer's awards`}
          />
          <Stat label="Median award value" value={randShort(summary.medianValue)} note="Of awards that publish a value" />
          <Stat label="Highest score" value={summary.maxScore} note="out of 100" />
        </div>

        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <section aria-labelledby="suppliers">
            <h2 id="suppliers" className="text-2xl">Suppliers awarded most often</h2>
            <p className="mb-3 text-sm text-muted">All years in the data. R7 counts repeat wins within 24 months.</p>
            <ol className="card divide-y divide-line">
              {suppliers.map((s) => (
                <li key={s.id} className="p-4">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-semibold text-ink-strong">{s.name}</span>
                    <span className="shrink-0 font-mono text-sm">{count(s.awards)} awards</span>
                  </div>
                  <div className="mt-2">
                    <Bar fraction={s.awards / topCount} label={`${s.awards} awards`} tone="muted" />
                  </div>
                  <p className="mt-1.5 text-sm text-muted">{count(s.flagged)} with red flags</p>
                </li>
              ))}
            </ol>
          </section>

          <section aria-labelledby="awards">
            <h2 id="awards" className="text-2xl">Awards by risk score</h2>
            <p className="mb-3 text-sm text-muted">{count(rows.length)} awards from this buyer.</p>
            <div className="space-y-3">
              {rows.slice(0, shown).map((a) => (
                <TenderCard key={a.id} award={a} rules={state.rules} />
              ))}
            </div>
            {shown < rows.length ? (
              <button type="button" className="btn btn-ghost mt-4 w-full" onClick={() => setShown((s) => s + PAGE)}>
                Show {Math.min(PAGE, rows.length - shown)} more
              </button>
            ) : null}
          </section>
        </div>
      </div>
    </>
  );
}
