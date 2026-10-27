import { type ReactNode, useEffect, useState } from "react";
import { AnomalyPanel } from "../components/AnomalyPanel";
import { PriceChart } from "../components/PriceChart";
import { ScoreRing } from "../components/ScoreRing";
import { EmptyBlock, ErrorBlock, LoadingBlock, PageTitle, SeverityChip } from "../components/ui";
import { DataError, loadDetail } from "../data/load";
import type { AwardDetail, AwardRow, RuleOutcome, SupplierMatch } from "../data/types";
import { useIndex } from "../data/useIndex";
import { explain } from "../lib/explain";
import { count, date, percent, rand } from "../lib/format";
import { Link, href, usePageFocus } from "../router";


type DetailState = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; detail: AwardDetail };

function useDetail(award: AwardRow | undefined) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<DetailState>({ status: "loading" });
  useEffect(() => {
    if (!award) return;
    let live = true;
    setState({ status: "loading" });
    loadDetail(award.id, award.shard).then(
      (detail) => live && setState({ status: "ready", detail }),
      (err: unknown) => {
        if (!live) return;
        console.error(err);
        setState({ status: "error", message: err instanceof DataError ? err.message : "Unexpected error loading this award." });
      },
    );
    return () => {
      live = false;
    };
  }, [award, attempt]);
  return { state, retry: () => setAttempt((n) => n + 1) };
}

export function TenderDetail({ id }: { id: string }) {
  const index = useIndex();
  usePageFocus(`tender:${id}:${index.status}`);
  const award = index.status === "ready" ? index.index.awards.find((a) => a.id === id) : undefined;
  const { state, retry } = useDetail(award);

  if (index.status === "loading") return <LoadingBlock label="Loading award" />;
  if (index.status === "error") return <ErrorBlock message={index.message} onRetry={index.retry} />;
  if (!award) {
    return (
      <>
        <PageTitle eyebrow="Tender">Award not found</PageTitle>
        <EmptyBlock title="There is no award with this reference in the current data.">
          <p>
            It may have been removed in the latest update, or the link is incomplete.{" "}
            <Link to={href.tenders()} className="underline">
              Browse all tenders
            </Link>
            .
          </p>
        </EmptyBlock>
      </>
    );
  }

  const others = index.index.awards.filter((a) => a.supplier_id === award.supplier_id && a.id !== award.id);

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-muted">
        <ol className="flex flex-wrap gap-1">
          <li>
            <Link to={href.tenders()} className="underline underline-offset-4">Tenders</Link> <span aria-hidden="true">/</span>
          </li>
          <li>
            <Link to={href.buyer(award.buyer_id)} className="underline underline-offset-4">{award.buyer}</Link>{" "}
            <span aria-hidden="true">/</span>
          </li>
          <li aria-current="page" className="font-mono">{award.ocid}</li>
        </ol>
      </nav>
      <PageTitle>{award.title || award.ocid}</PageTitle>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-8">
          <section aria-labelledby="assessment" className="card p-5">
            <h2 id="assessment" className="sr-only">Risk assessment</h2>
            {state.status === "loading" && <LoadingBlock label="Loading the rule breakdown" lines={3} />}
            {state.status === "error" && <ErrorBlock message={state.message} onRetry={retry} />}
            {state.status === "ready" && <Assessment detail={state.detail} />}
          </section>

          {state.status === "ready" && <Breakdown detail={state.detail} />}
          {state.status === "ready" && (
            <AnomalyPanel
              signal={state.detail.anomaly}
              priced={index.index.awards.filter((a) => a.anomaly_pct !== null).length}
            />
          )}
        </div>

        <aside className="space-y-4">
          <section aria-labelledby="facts" className="card p-5">
            <h2 id="facts" className="mb-3 text-xl">Award</h2>
            <dl className="space-y-2 text-sm">
              <Fact label="Award value"><span className="font-mono text-base text-ink-strong">{rand(award.value)}</span></Fact>
              <Fact label="Buyer">
                <Link to={href.buyer(award.buyer_id)} className="underline underline-offset-4">{award.buyer}</Link>
              </Fact>
              <Fact label="Category">{award.category ?? "Not published"}</Fact>
              <Fact label="Tender closed">{date(award.close_date)}</Fact>
              <Fact label="OCDS reference"><span className="break-all font-mono">{award.ocid}</span></Fact>
            </dl>
          </section>

          <section aria-labelledby="supplier" className="card p-5">
            <h2 id="supplier" className="mb-1 text-xl">Winning supplier</h2>
            <p className="font-semibold text-ink-strong">{award.supplier}</p>
            {state.status === "ready" ? (
              <SupplierMatchPanel match={state.detail.supplier_match ?? null} />
            ) : (
              <p className="mt-2 text-sm text-muted">
                Supplier match details load with the award analysis.
              </p>
            )}
            <h3 className="mt-4 text-sm font-semibold text-ink-strong">
              Other awards to this supplier ({count(others.length)})
            </h3>
            {others.length === 0 ? (
              <p className="text-sm text-muted">None in the current data.</p>
            ) : (
              <ul className="mt-1 space-y-1 text-sm">
                {others.slice(0, 6).map((o) => (
                  <li key={o.id}>
                    <Link to={href.tender(o.id)} className="underline decoration-line underline-offset-4 hover:decoration-ink-strong">
                      {o.title || o.ocid}
                    </Link>{" "}
                    <span className="text-muted">· {o.buyer}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="concern" className="card p-5 text-sm">
            <h2 id="concern" className="mb-1 text-xl">Know more about this award?</h2>
            <p>
              Take it to{" "}
              <a className="underline" href="https://www.corruptionwatch.org.za/" rel="noopener noreferrer">Corruption Watch</a> or{" "}
              <a className="underline" href="https://amabhungane.org/" rel="noopener noreferrer">amaBhungane</a>. This site does
              not collect tips.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}

function SupplierMatchPanel({
  match,
}: {
    match: SupplierMatch | null;
}) {
  if (match === null) {
    return (
      <p className="mt-2 text-sm text-muted">
        Not matched to CIPC yet. The company age, director and sector checks (R1 to R6 and R9) run once registry data is loaded.
      </p>
    );
  }

  // Similarity is not a probability that the company identity is correct.
  const score = Math.round(match.confidence * 100);

  let message: string;
  switch (match.status) {
    case "exact":
      message = "Exact name match after normalization.";
      break;
    case "strong_fuzzy":
      message = "Possible name match; manual review is recommended.";
      break;
    case "needs_review":
      message = "Potential match requires manual review.";
      break;
    case "no_match":
      message = "No company match found in the available data.";
      break;
  }

  return (
    <div className="mt-2 rounded-md bg-sunken p-3 text-sm">
      <p className="font-semibold text-ink-strong">{message}</p>

      {match.matched_company_name !== null && (
        <p className="mt-1">
          Suggested company: {match.matched_company_name}
        </p>
      )}

      {match.status !== "no_match" && (
        <p className="mt-1 text-muted">
          Name-similarity score: {score}/100. This is not a probability of identity.
        </p>
      )}

      <p className="mt-1 text-muted">
        Source: {match.source === "sample" ? "demonstration sample" : match.source}
      </p>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Assessment({ detail }: { detail: AwardDetail }) {
  const fired = detail.breakdown.filter((r) => r.fired);
  const evaluated = detail.breakdown.filter((r) => r.evaluated).length;
  return (
    <div className="flex flex-wrap items-center gap-6">
      <ScoreRing score={detail.score} level={detail.level} />
      <div className="min-w-0 flex-1 basis-60 text-sm">
        <p className="text-ink-strong">
          {fired.length === 0 ? "No red flags fired." : `${fired.length} red flag${fired.length === 1 ? "" : "s"} fired, ${detail.score} points.`}{" "}
          {evaluated} of {detail.breakdown.length} rules could be checked ({percent(detail.coverage)}).
        </p>
        <p className="mt-1 text-muted">
          A flag needs 50 points and an alert 75. A low score with low coverage means missing data, not a clean award.
        </p>
      </div>
    </div>
  );
}

function Breakdown({ detail }: { detail: AwardDetail }) {
  const fired = detail.breakdown.filter((r) => r.fired);
  const clear = detail.breakdown.filter((r) => r.evaluated && !r.fired);
  const unevaluated = detail.breakdown.filter((r) => !r.evaluated);
  const price = detail.breakdown.find((r) => (r.rule_id === "R10" || r.rule_id === "R11") && r.fired);

  return (
    <>
      <section aria-labelledby="flags">
        <h2 id="flags" className="mb-3 text-2xl">Red flags</h2>
        {fired.length === 0 ? (
          <EmptyBlock title="No rule fired for this award." />
        ) : (
          <ul className="space-y-3">
            {fired.map((r) => (
              <RuleItem key={r.rule_id} r={r} />
            ))}
          </ul>
        )}
      </section>

      {price ? <PriceChart evidence={price.evidence} /> : null}

      {clear.length > 0 && (
        <section aria-labelledby="checked">
          <h2 id="checked" className="mb-3 text-2xl">Checked, no flag</h2>
          <ul className="card divide-y divide-line">
            {clear.map((r) => (
              <li key={r.rule_id} className="p-4 text-sm">
                <p className="font-semibold text-ink-strong">
                  <span className="font-mono">{r.rule_id}</span> {r.title}
                </p>
                <p className="mt-0.5 text-muted">{explain(r)}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {unevaluated.length > 0 && (
        <details className="card p-4">
          <summary className="cursor-pointer font-semibold text-ink-strong">
            {unevaluated.length} rules could not be checked
          </summary>
          <ul className="mt-3 space-y-2 text-sm">
            {unevaluated.map((r) => (
              <li key={r.rule_id}>
                <span className="font-mono">{r.rule_id}</span> {r.title}: <span className="text-muted">{explain(r).replace(/^Not evaluated: /, "")}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function RuleItem({ r }: { r: RuleOutcome }) {
  return (
    <li className="card border-l-4 p-4" style={{ borderLeftColor: `var(--sev-${r.severity})` }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-ink-strong">
          <span className="font-mono">{r.rule_id}</span> {r.title}
        </p>
        <span className="flex items-center gap-2">
          <SeverityChip severity={r.severity}>{r.severity}</SeverityChip>
          <span className="font-mono font-semibold text-ink-strong">+{r.points}</span>
        </span>
      </div>
      <p className="mt-1 text-sm">{explain(r)}</p>
      {r.needs_review ? <p className="mt-1 text-sm font-semibold">Needs human review before any conclusion.</p> : null}
    </li>
  );
}
