import type { ReactNode } from "react";
import { Link, type Route, href } from "../router";

const NAV: { label: string; to: string; match: Route["name"][] }[] = [
  { label: "Overview", to: href.overview(), match: ["overview", "buyer"] },
  { label: "Tenders", to: href.tenders(), match: ["tenders", "tender"] },
];

export function Shell({ route, children }: { route: Route; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-ink-strong focus:px-3 focus:py-2 focus:text-canvas"
      >
        Skip to content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to={href.overview()} className="flex items-center gap-2 no-underline">
            <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
              <rect width="32" height="32" rx="6" fill="currentColor" className="text-ink-strong" />
              <path d="M9 22V10h8a4 4 0 0 1 0 8H9" fill="none" stroke="var(--canvas)" strokeWidth="2.5" strokeLinejoin="round" />
              <circle cx="23" cy="22" r="2.5" fill="var(--risk)" />
            </svg>
            <span className="font-serif text-lg text-ink-strong">Tender Risk Monitor</span>
          </Link>
          <nav aria-label="Main">
            <ul className="flex gap-1">
              {NAV.map((item) => {
                const current = item.match.includes(route.name);
                return (
                  <li key={item.to}>
                    <Link
                      to={item.to}
                      aria-current={current ? "page" : undefined}
                      className={`inline-flex min-h-10 items-center rounded-md px-3 text-sm font-semibold no-underline hover:bg-sunken ${
                        current ? "bg-sunken text-ink-strong" : "text-muted"
                      }`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {children}
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto max-w-6xl space-y-2 px-4 py-6 text-sm text-muted">
          <p>
            Risk scores are indicators for review, not findings of wrongdoing. Each score shows the rules behind it and how
            much of the data could be checked.
          </p>
          <p>
            Data:{" "}
            <a className="underline" href="https://data.open-contracting.org/en/publication/143" rel="noopener noreferrer">
              National Treasury eTenders OCDS feed
            </a>{" "}
            (PDDL). Method:{" "}
            <a
              className="underline"
              href="https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Rule-Catalogue"
              rel="noopener noreferrer"
            >
              rule catalogue
            </a>
            . CTU SE2 Capstone, Group 2.
          </p>
          <nav aria-label="Legal">
            <ul className="flex flex-wrap gap-x-4 gap-y-1">
              <li>
                <Link to={href.privacy()} className="underline">Privacy and cookies</Link>
              </li>
              <li>
                <Link to={href.terms()} className="underline">Terms of use</Link>
              </li>
            </ul>
          </nav>
        </div>
      </footer>
    </div>
  );
}
