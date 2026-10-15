import { useEffect, useMemo, useState } from "react";
import { TenderCard } from "../components/TenderCard";
import { EmptyBlock, ErrorBlock, LoadingBlock, PageTitle } from "../components/ui";
import { useIndex } from "../data/useIndex";
import { type ListFilter, filterAwards } from "../lib/aggregate";
import { SHORT_LABEL } from "../lib/explain";
import { count } from "../lib/format";
import { navigate, usePageFocus } from "../router";

const PAGE = 25;
const SORTS: { value: ListFilter["sort"]; label: string }[] = [
  { value: "score", label: "Risk score" },
  { value: "value", label: "Award value" },
  { value: "date", label: "Most recent" },
  { value: "anomaly", label: "Most unusual price" },
];

function readFilter(search: URLSearchParams): ListFilter & { flagged: boolean } {
  const sort = search.get("sort");
  const min = Number.parseInt(search.get("min") ?? "0", 10);
  return {
    q: (search.get("q") ?? "").slice(0, 120),
    rules: search.getAll("rule").filter((r) => /^R\d{1,2}$/.test(r)),
    minScore: Number.isFinite(min) ? Math.max(0, Math.min(100, min)) : 0,
    sort: sort === "value" || sort === "date" || sort === "anomaly" ? sort : "score",
    flagged: search.get("flagged") === "1",
  };
}

function writeFilter(f: ListFilter & { flagged: boolean }) {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  for (const r of f.rules) p.append("rule", r);
  if (f.minScore) p.set("min", String(f.minScore));
  if (f.sort !== "score") p.set("sort", f.sort);
  if (f.flagged) p.set("flagged", "1");
  const qs = p.toString();
  navigate(qs ? `/tenders?${qs}` : "/tenders", { replace: true });
}

export function Tenders({ search }: { search: URLSearchParams }) {
  const state = useIndex();
  usePageFocus(`tenders:${state.status}`);
  const filter = readFilter(search);
  const [query, setQuery] = useState(filter.q);
  const [shown, setShown] = useState(PAGE);
  const key = search.toString();

  // Debounce typing into the URL so every keystroke does not refilter 9,500 rows.
  useEffect(() => {
    if (query === filter.q) return;
    const t = setTimeout(() => writeFilter({ ...filter, q: query.trim() }), 250);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => setShown(PAGE), [key]);

  const results = useMemo(() => {
    if (state.status !== "ready") return [];
    const rows = filterAwards(state.index.awards, filter);
    return filter.flagged ? rows.filter((a) => a.fired.length > 0) : rows;
  }, [state, key]);

  const toggleRule = (id: string) =>
    writeFilter({ ...filter, rules: filter.rules.includes(id) ? filter.rules.filter((r) => r !== id) : [...filter.rules, id] });

  const active = filter.q || filter.rules.length || filter.minScore || filter.flagged;

  return (
    <>
      <PageTitle eyebrow="eTenders awards">Tenders</PageTitle>

      {state.status === "loading" && <LoadingBlock label="Loading tenders" lines={6} />}
      {state.status === "error" && <ErrorBlock message={state.message} onRetry={state.retry} />}
      {state.status === "ready" && (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <form role="search" aria-label="Filter tenders" className="space-y-5 lg:sticky lg:top-4 lg:self-start" onSubmit={(e) => e.preventDefault()}>
            <label className="block text-sm font-semibold text-ink-strong">
              Search
              <input
                className="field mt-1 w-full font-normal"
                type="search"
                value={query}
                maxLength={120}
                placeholder="Tender, buyer or supplier"
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>

            <fieldset>
              <legend className="text-sm font-semibold text-ink-strong">Red flags</legend>
              <p className="mb-2 text-xs text-muted">Show awards with any selected flag.</p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  aria-pressed={filter.flagged}
                  onClick={() => writeFilter({ ...filter, flagged: !filter.flagged })}
                  className={`chip min-h-8 border ${filter.flagged ? "border-ink-strong bg-ink-strong text-canvas" : "border-control bg-surface text-ink"}`}
                >
                  Any flag
                </button>
                {state.index.rules
                  .filter((r) => (state.index.summary.fired[r.id] ?? 0) > 0)
                  .map((r) => {
                    const on = filter.rules.includes(r.id);
                    return (
                      <button
                        key={r.id}
                        type="button"
                        aria-pressed={on}
                        title={r.title}
                        onClick={() => toggleRule(r.id)}
                        className={`chip min-h-8 border ${on ? "border-ink-strong bg-ink-strong text-canvas" : "border-control bg-surface text-ink"}`}
                      >
                        {SHORT_LABEL[r.id] ?? r.id}
                      </button>
                    );
                  })}
              </div>
            </fieldset>

            <label className="block text-sm font-semibold text-ink-strong">
              Minimum score
              <select
                className="field mt-1 w-full font-normal"
                value={filter.minScore}
                onChange={(e) => writeFilter({ ...filter, minScore: Number(e.target.value) })}
              >
                {[0, 3, 8, 15, 20, 25, 50, 75].map((v) => (
                  <option key={v} value={v}>
                    {v === 0 ? "Any score" : `${v} or more`}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-semibold text-ink-strong">
              Sort by
              <select
                className="field mt-1 w-full font-normal"
                value={filter.sort}
                onChange={(e) => writeFilter({ ...filter, sort: e.target.value as ListFilter["sort"] })}
              >
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              className="btn btn-ghost w-full"
              disabled={!active}
              title={active ? undefined : "No filters are set"}
              onClick={() => {
                setQuery("");
                writeFilter({ q: "", rules: [], minScore: 0, sort: filter.sort, flagged: false });
              }}
            >
              Clear filters
            </button>
          </form>

          <section aria-labelledby="results">
            <h2 id="results" className="sr-only">Results</h2>
            <p className="mb-3 text-sm text-muted" aria-live="polite">
              {count(results.length)} of {count(state.index.awards.length)} awards
            </p>
            {results.length === 0 ? (
              <EmptyBlock title="No awards match these filters.">
                <p>Try fewer red flags, a lower minimum score, or a shorter search.</p>
              </EmptyBlock>
            ) : (
              <>
                <div className="space-y-3">
                  {results.slice(0, shown).map((a) => (
                    <TenderCard key={a.id} award={a} rules={state.rules} />
                  ))}
                </div>
                {shown < results.length ? (
                  <button type="button" className="btn btn-ghost mt-4 w-full" onClick={() => setShown((s) => s + PAGE)}>
                    Show {Math.min(PAGE, results.length - shown)} more
                  </button>
                ) : null}
              </>
            )}
          </section>
        </div>
      )}
    </>
  );
}
