import type { AwardRow, RuleInfo } from "../data/types";
import { date, rand } from "../lib/format";
import { Link, href } from "../router";
import { FlagChips } from "./ui";

export function ScoreBadge({ score, level }: { score: number; level: string }) {
  const tone = level === "none" ? "border-control text-ink-strong" : "border-risk text-risk";
  return (
    <span className={`inline-flex shrink-0 flex-col items-center rounded-md border px-2 py-1 leading-none ${tone}`}>
      <span className="font-mono text-lg font-semibold">{score}</span>
      <span className="mt-0.5 text-[0.625rem] font-semibold uppercase tracking-wide">score</span>
    </span>
  );
}

export function TenderCard({ award, rules }: { award: AwardRow; rules: Map<string, RuleInfo> }) {
  return (
    <article className="card p-4 transition-colors hover:border-control">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow truncate">{award.buyer}</p>
          <h3 className="mt-1 font-semibold leading-snug text-ink-strong">
            <Link to={href.tender(award.id)} className="underline decoration-line underline-offset-4 hover:decoration-ink-strong">
              {award.title || award.ocid}
            </Link>
          </h3>
        </div>
        <ScoreBadge score={award.score} level={award.level} />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted">Award value</dt>
          <dd className="font-mono text-ink-strong">{rand(award.value)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-muted">Supplier</dt>
          <dd className="truncate">{award.supplier}</dd>
        </div>
        <div>
          <dt className="text-muted">Closed</dt>
          <dd>{date(award.close_date)}</dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <FlagChips fired={award.fired} rules={rules} />
        {award.anomaly_pct !== null && award.anomaly_pct >= 99 ? (
          <span className="chip border border-control text-ink" title="Isolation Forest signal, not part of the score">
            Unusual price: top 1%
          </span>
        ) : null}
      </div>
    </article>
  );
}
