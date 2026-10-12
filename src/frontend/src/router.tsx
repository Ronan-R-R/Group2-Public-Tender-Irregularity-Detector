import { type AnchorHTMLAttributes, type MouseEvent, useEffect, useSyncExternalStore } from "react";

// A deliberately small router: four routes do not justify a dependency.
// Cloudflare Pages serves index.html for unknown paths, so deep links work.

export type Route =
  | { name: "overview" }
  | { name: "tenders"; search: URLSearchParams }
  | { name: "tender"; id: string }
  | { name: "buyer"; id: string }
  | { name: "not-found" };

export function parse(pathname: string, search: string): Route {
  const parts = pathname.split("/").filter(Boolean);
  try {
    if (parts.length === 0) return { name: "overview" };
    if (parts[0] === "tenders" && parts.length === 1) return { name: "tenders", search: new URLSearchParams(search) };
    if (parts[0] === "tenders" && parts.length === 2) return { name: "tender", id: decodeURIComponent(parts[1]!) };
    if (parts[0] === "buyers" && parts.length === 2) return { name: "buyer", id: decodeURIComponent(parts[1]!) };
  } catch {
    // Malformed percent-encoding in a hand-typed URL.
  }
  return { name: "not-found" };
}

export const href = {
  overview: () => "/",
  tenders: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return qs ? `/tenders?${qs}` : "/tenders";
  },
  tender: (id: string) => `/tenders/${encodeURIComponent(id)}`,
  buyer: (id: string) => `/buyers/${encodeURIComponent(id)}`,
};

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
}

const snapshot = () => location.pathname + location.search;

export function navigate(to: string, opts: { replace?: boolean } = {}) {
  if (to === snapshot()) return;
  if (opts.replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  notify();
}

export function useRoute(): Route {
  const key = useSyncExternalStore(subscribe, snapshot, snapshot);
  const [path, query = ""] = key.split("?");
  return parse(path ?? "/", query ? `?${query}` : "");
}

/** Scroll to top and move focus to the main heading on page change. */
export function usePageFocus(dep: string) {
  useEffect(() => {
    window.scrollTo(0, 0);
    document.querySelector<HTMLElement>("main h1")?.focus();
  }, [dep]);
}

export function Link({ to, onClick, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate(to);
  };
  return <a href={to} onClick={handle} {...rest} />;
}
