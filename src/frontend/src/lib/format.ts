const zarFull = new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 });
// Whole numbers use en-ZA grouping (spaces). Decimals always use a point,
// because en-ZA's decimal comma would sit next to "R14.9m" style figures.
const num = new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 });

function oneDecimal(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  const whole = Math.trunc(Math.abs(rounded));
  const tenth = Math.round((Math.abs(rounded) - whole) * 10);
  return `${num.format(whole)}${tenth ? `.${tenth}` : ""}`;
}

export function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/** R 142 500 000 */
export function rand(value: string | number | null | undefined): string {
  const n = toNumber(value);
  return n === null ? "Not published" : zarFull.format(n);
}

/** R142.5m, R14.6bn: for tiles and charts where space is tight. */
export function randShort(value: string | number | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return "Not published";
  const abs = Math.abs(n);
  const unit = abs >= 1e9 ? ["bn", 1e9] : abs >= 1e6 ? ["m", 1e6] : abs >= 1e3 ? ["k", 1e3] : null;
  if (!unit) return zarFull.format(n);
  const [suffix, size] = unit as [string, number];
  const scaled = n / size;
  const digits = Math.abs(scaled) >= 100 ? 0 : 1;
  return `R${scaled.toFixed(digits)}${suffix}`;
}

export function count(n: number): string {
  return num.format(n);
}

export function percent(fraction: number): string {
  return `${oneDecimal(fraction * 100)}%`;
}

export function signedPercent(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${oneDecimal(value)}%`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "Not published";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-ZA", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function levelLabel(level: string): string {
  return level === "alert" ? "Alert" : level === "flag" ? "Flagged" : "Below flag level";
}
