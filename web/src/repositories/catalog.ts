import { labelFrom } from "../lib/format";
import type {
  AdvisorStatus,
  Filters,
  JobStatus,
  ListingDetail,
  ListingPage,
  PicksPage,
  SourceInfo,
  Stats,
} from "../types";

/** Без этого заголовка сервер отклоняет POST: так чужая страница не запустит задачу. */
const UI_HEADER = { "X-Skelbiu-Request": "1" } as const;

const STATUS_TEXT: Record<number, string> = {
  401: "Нужен логин и пароль — обнови страницу",
  403: "Сервер отклонил запрос",
  404: "Не найдено",
  422: "Недопустимое значение",
};

const FIELD_LABEL: Record<string, string> = {
  listing_id: "номер объявления",
  q: "поиск",
  min_price: "цена от",
  max_price: "цена до",
  city: "город",
  socket: "сокет",
  source: "источник",
  advice: "совет модели",
  min_score: "оценка от",
  min_profit: "маржа от",
  page: "страница",
  limit: "размер страницы",
};

function describeValidation(detail: unknown[]): string {
  const fields = detail
    .map((row) => {
      const loc = (row as { loc?: unknown[] })?.loc;
      const name = Array.isArray(loc) ? String(loc[loc.length - 1]) : "";
      return labelFrom(FIELD_LABEL, name);
    })
    .filter(Boolean);
  const unique = [...new Set(fields)];
  return unique.length ? `${STATUS_TEXT[422]}: ${unique.join(", ")}` : STATUS_TEXT[422];
}

async function readError(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return describeValidation(data.detail);
  } catch {
    /* не JSON */
  }
  return STATUS_TEXT[res.status] || `Ошибка сервера (${res.status})`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { credentials: "same-origin", ...init });
  } catch {
    throw new Error("Нет связи с сервером");
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<T>;
}

const getJson = <T>(url: string) => request<T>(url);
const postJson = <T>(url: string) => request<T>(url, { method: "POST", headers: UI_HEADER });
const listingUrl = (id: string) => `/api/listings/${encodeURIComponent(id)}`;

export const catalog = {
  stats: () => getJson<Stats>("/api/stats"),
  filters: () => getJson<Filters>("/api/filters"),
  sources: () => getJson<{ items: SourceInfo[] }>("/api/sources"),
  picks: (limit = 8) => getJson<PicksPage>(`/api/picks?limit=${limit}`),
  listings(params: Record<string, string | number | undefined>, init?: RequestInit) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === "") continue;
      query.set(key, String(value));
    }
    return request<ListingPage>(`/api/listings?${query.toString()}`, init);
  },
  listing: (id: string) => getJson<ListingDetail>(listingUrl(id)),
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
  adviseListing: (id: string) => postJson<ListingDetail>(`${listingUrl(id)}/advise`),
};
