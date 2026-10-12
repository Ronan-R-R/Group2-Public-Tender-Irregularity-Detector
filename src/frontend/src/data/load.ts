import type { AwardDetail, Index } from "./types";

export class DataError extends Error {}

async function getJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { headers: { Accept: "application/json" }, ...(signal ? { signal } : {}) });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new DataError("Could not reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    throw new DataError(
      res.status === 404
        ? "The data file is missing. The latest deploy may still be running."
        : `The server returned an error (HTTP ${res.status}).`,
    );
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new DataError("The data file could not be read.");
  }
}

let indexPromise: Promise<Index> | null = null;

export function loadIndex(): Promise<Index> {
  if (!indexPromise) {
    indexPromise = getJSON<Index>("/data/index.json").then((index) => {
      if (index.schema_version !== 1 || !Array.isArray(index.awards)) {
        throw new DataError("The data file has an unexpected format.");
      }
      return index;
    });
    // A failed load must not be cached, or "Try again" could never succeed.
    indexPromise.catch(() => {
      indexPromise = null;
    });
  }
  return indexPromise;
}

const shards = new Map<string, Promise<Record<string, AwardDetail>>>();

export async function loadDetail(id: string, shard: string): Promise<AwardDetail> {
  if (!/^[0-9a-f]{2}$/.test(shard)) throw new DataError("Invalid award reference.");
  let pending = shards.get(shard);
  if (!pending) {
    pending = getJSON<Record<string, AwardDetail>>(`/data/details/${shard}.json`);
    shards.set(shard, pending);
    pending.catch(() => shards.delete(shard));
  }
  const records = await pending;
  const detail = records[id];
  if (!detail) throw new DataError("This award is missing from the data. It may have been removed in the latest update.");
  return detail;
}

export function resetCachesForTests(): void {
  indexPromise = null;
  shards.clear();
}
