/** Репозиторий над HTTP API. Виды не ходят в fetch напрямую. */

import type {
  AdvisorStatus,
  Filters,
  JobStatus,
  ListingDetail,
  ListingPage,
  SourceInfo,
  Stats,
} from "../types";

async function readError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
  } catch {
    /* сырой текст */
  }
  return text || res.statusText;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<T>;
}

async function postJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<T>;
}

export const catalog = {
  stats: () => getJson<Stats>("/api/stats"),
  filters: () => getJson<Filters>("/api/filters"),
  sources: () => getJson<{ items: SourceInfo[] }>("/api/sources"),
  listings(params: Record<string, string | number | undefined>) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === "") continue;
      query.set(key, String(value));
    }
    return getJson<ListingPage>(`/api/listings?${query.toString()}`);
  },
  listing: (id: string) => getJson<ListingDetail>(`/api/listings/${id}`),
  analyzeStatus: () => getJson<JobStatus>("/api/analyze"),
  detailsStatus: () => getJson<JobStatus>("/api/details"),
  advisorStatus: () => getJson<AdvisorStatus>("/api/advise"),
  async adviseJob() {
    const status = await getJson<AdvisorStatus>("/api/advise");
    return (
      status.job ?? {
        running: false,
        kind: null,
        done: 0,
        total: 0,
        analyzed: 0,
        error: null,
        stats: null,
      }
    );
  },
  analyze: () => postJson<JobStatus>("/api/analyze"),
  details: () => postJson<JobStatus>("/api/details"),
  advise: () => postJson<JobStatus>("/api/advise"),
  adviseListing: (id: string) => postJson<ListingDetail>(`/api/listings/${id}/advise`),
};
