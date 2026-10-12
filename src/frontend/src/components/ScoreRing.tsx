import { levelLabel } from "../lib/format";

export function ScoreRing({ score, level, max = 100 }: { score: number; level: string; max?: number }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const filled = (Math.max(0, Math.min(score, max)) / max) * c;
  const tone = level === "none" ? "var(--ink-strong)" : "var(--risk)";
  return (
    <figure className="flex items-center gap-4">
      <svg width="88" height="88" viewBox="0 0 88 88" role="img" aria-label={`Risk score ${score} out of ${max}, ${levelLabel(level)}`}>
        <circle cx="44" cy="44" r={r} fill="none" stroke="var(--sunken)" strokeWidth="8" />
        <circle
          cx="44"
          cy="44"
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${c}`}
          transform="rotate(-90 44 44)"
        />
        <text x="44" y="46" textAnchor="middle" dominantBaseline="middle" fontSize="24" fontWeight="600" fill="var(--ink-strong)" fontFamily="var(--font-mono)">
          {score}
        </text>
        <text x="44" y="64" textAnchor="middle" fontSize="9" fill="var(--muted)">
          / {max}
        </text>
      </svg>
      <figcaption>
        <p className="text-sm font-semibold uppercase tracking-wide" style={{ color: tone }}>
          {levelLabel(level)}
        </p>
      </figcaption>
    </figure>
  );
}
