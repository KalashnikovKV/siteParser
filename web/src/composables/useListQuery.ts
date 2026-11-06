import { reactive, watch } from "vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";
import type { QueryState } from "../types";

/** Нейтральные значения полей. Стартовый «Топ модели» — только для пустого URL. */
export const DEFAULTS: QueryState = {
  q: "",
  min_price: "",
  max_price: "",
  city: "",
  socket: "",
  source: "",
  potential: "",
  advice: "",
  min_score: "",
  min_profit: "",
  has_description: "",
  preset: "",
  kind: "desktop",
  sort: "ai",
  page: 1,
};

export const HOME_QUERY: QueryState = {
  ...DEFAULTS,
  preset: "picks",
  sort: "ai",
  page: 1,
};

export const PRESET_LABELS: Record<string, string> = {
  picks: "Топ модели",
  upgrade: "Есть апгрейд",
  cheap: "До 250 €",
  margin: "Лучшая маржа",
  fresh: "Свежие",
};

/** Полный каталог без категории. */
export const ALL_LISTINGS: QueryState = {
  ...DEFAULTS,
  preset: "",
  sort: "ai",
  page: 1,
};

function one(raw: LocationQuery, key: string): string | undefined {
  const value = raw[key];
  return typeof value === "string" ? value : undefined;
}

function isEmptyHome(raw: LocationQuery): boolean {
  return Object.keys(raw).length === 0;
}

export function queryFromRoute(raw: LocationQuery): QueryState {
  if (isEmptyHome(raw)) return { ...HOME_QUERY };

  const page = Number(one(raw, "page"));
  const viewAll = one(raw, "view") === "all";
  return {
    q: one(raw, "q") ?? DEFAULTS.q,
    min_price: one(raw, "min_price") ?? DEFAULTS.min_price,
    max_price: one(raw, "max_price") ?? DEFAULTS.max_price,
    city: one(raw, "city") ?? DEFAULTS.city,
    socket: one(raw, "socket") ?? DEFAULTS.socket,
    source: one(raw, "source") ?? DEFAULTS.source,
    potential: one(raw, "potential") ?? DEFAULTS.potential,
    advice: one(raw, "advice") ?? DEFAULTS.advice,
    min_score: one(raw, "min_score") ?? DEFAULTS.min_score,
    min_profit: one(raw, "min_profit") ?? DEFAULTS.min_profit,
    has_description: one(raw, "has_description") ?? DEFAULTS.has_description,
    // Явный view=all или отсутствие preset в URL — без категории.
    // Нельзя подставлять picks, иначе ?max_price=&sort= ломается пресетом.
    preset: viewAll ? "" : (one(raw, "preset") ?? ""),
    kind: one(raw, "kind") ?? DEFAULTS.kind,
    sort: one(raw, "sort") ?? DEFAULTS.sort,
    page: Number.isFinite(page) && page >= 1 ? Math.floor(page) : DEFAULTS.page,
  };
}

function isHomeState(state: QueryState): boolean {
  return (
    state.preset === HOME_QUERY.preset &&
    !state.q &&
    !state.min_price &&
    !state.max_price &&
    !state.city &&
    !state.socket &&
    !state.source &&
    !state.potential &&
    !state.advice &&
    !state.min_score &&
    !state.min_profit &&
    !state.has_description &&
    state.kind === HOME_QUERY.kind &&
    state.sort === HOME_QUERY.sort &&
    state.page === 1
  );
}

export function queryToRoute(state: QueryState): Record<string, string> {
  // Домашний топ модели → чистый URL без параметров.
  if (isHomeState(state)) return {};

  const out: Record<string, string> = {};
  for (const key of Object.keys(DEFAULTS) as (keyof QueryState)[]) {
    const value = String(state[key]);
    if (value !== "" && value !== String(DEFAULTS[key])) out[key] = value;
  }
  // Каталог без категории — иначе пустой URL снова станет «Топ модели».
  if (!state.preset) out.view = "all";
  return out;
}

function fingerprint(state: QueryState) {
  return JSON.stringify(queryToRoute(state));
}

export function useListQuery() {
  const route = useRoute();
  const router = useRouter();
  const query = reactive<QueryState>(queryFromRoute(route.query));

  watch(
    () => route.query,
    (raw) => {
      const next = queryFromRoute(raw);
      if (fingerprint(next) !== fingerprint(query)) Object.assign(query, next);
    },
  );

  watch(
    query,
    () => {
      if (route.name !== "list") return;
      if (fingerprint(queryFromRoute(route.query)) === fingerprint(query)) return;
      router.replace({ query: queryToRoute(query) });
    },
    { deep: true },
  );

  function clearFilters() {
    Object.assign(query, { ...ALL_LISTINGS });
  }

  function applyPreset(name: string) {
    Object.assign(query, {
      ...DEFAULTS,
      preset: name,
      page: 1,
    });
  }

  function showAll() {
    Object.assign(query, { ...ALL_LISTINGS });
  }

  return { query, clearFilters, applyPreset, showAll };
}
