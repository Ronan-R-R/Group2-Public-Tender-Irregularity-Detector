import type { ReactNode } from "react";
import type { RuleInfo, Severity } from "../data/types";
import { SHORT_LABEL } from "../lib/explain";

export function PageTitle({ eyebrow, children }: { eyebrow?: ReactNode; children: ReactNode }) {
  return (
    <div className="mb-6">
      {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
      <h1 tabIndex={-1} className="text-3xl sm:text-4xl">
        {children}
      </h1>
    </div>
  );
}

export function SeverityChip({ severity, children }: { severity: Severity; children: ReactNode }) {
  return <span className={`chip sev-${severity}`}>{children}</span>;
}

export function FlagChips({ fired, rules }: { fired: string[]; rules: Map<string, RuleInfo> }) {
  if (fired.length === 0) return <span className="chip sev-ok">No red flags</span>;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Red flags">
      {fired.map((id) => {
        const r = rules.get(id);
        return (
          <li key={id}>
            <span className={`chip sev-${r?.severity ?? "low"}`} title={r?.title ?? id}>
              <span className="font-mono">{id}</span> {SHORT_LABEL[id] ?? r?.title ?? ""}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function Stat({ label, value, note, tone }: { label: string; value: ReactNode; note?: ReactNode; tone?: "risk" }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 font-serif text-3xl leading-tight ${tone === "risk" ? "text-risk" : "text-ink-strong"}`}>{value}</p>
      {note ? <p className="mt-1 text-sm text-muted">{note}</p> : null}
    </div>
  );
}

/** Horizontal bar; width is a share of the largest value in the set. */
export function Bar({ fraction, tone = "ink", label }: { fraction: number; tone?: "ink" | "risk" | "muted"; label: string }) {
  const width = `${Math.max(2, Math.min(100, fraction * 100)).toFixed(1)}%`;
  const color = tone === "risk" ? "bg-risk" : tone === "muted" ? "bg-control" : "bg-ink-strong";
  return (
    <div className="h-2 w-full overflow-hidden rounded-sm bg-sunken" role="img" aria-label={label}>
      <div className={`h-full ${color}`} style={{ width }} />
    </div>
  );
}

export function LoadingBlock({ label, lines = 4 }: { label: string; lines?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton h-16" aria-hidden="true" />
      ))}
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card border-risk p-6">
      <p className="font-semibold text-ink-strong">Something went wrong loading this page.</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry ? (
        <button type="button" className="btn btn-primary mt-4" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptyBlock({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card border-dashed p-6">
      <p className="font-semibold text-ink-strong">{title}</p>
      {children ? <div className="mt-2 text-sm">{children}</div> : null}
    </div>
  );
}
