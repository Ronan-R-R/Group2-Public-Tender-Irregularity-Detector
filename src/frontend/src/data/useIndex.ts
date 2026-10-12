import { useCallback, useEffect, useMemo, useState } from "react";
import { DataError, loadIndex } from "./load";
import type { Index, RuleInfo } from "./types";

export type IndexState =
  | { status: "loading" }
  | { status: "error"; message: string; retry: () => void }
  | { status: "ready"; index: Index; rules: Map<string, RuleInfo> };

export function useIndex(): IndexState {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ index: Index } | { error: string } | null>(null);
  const retry = useCallback(() => {
    setResult(null);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let live = true;
    loadIndex().then(
      (index) => live && setResult({ index }),
      (err: unknown) => {
        if (!live) return;
        console.error(err);
        setResult({ error: err instanceof DataError ? err.message : "Unexpected error while loading the data." });
      },
    );
    return () => {
      live = false;
    };
  }, [attempt]);

  return useMemo<IndexState>(() => {
    if (result === null) return { status: "loading" };
    if ("error" in result) return { status: "error", message: result.error, retry };
    return { status: "ready", index: result.index, rules: new Map(result.index.rules.map((r) => [r.id, r])) };
  }, [result, retry]);
}
