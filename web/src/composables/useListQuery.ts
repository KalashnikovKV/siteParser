import { reactive, watch } from "vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";
import type { QueryState } from "../types";

const DEFAULTS: QueryState = {
  q: "",
  min_price: "",
  max_price: "",
  city: "",
  socket: "",
  source: "",
  potential: "",
  kind: "desktop",
  sort: "score",
  page: 1,
};

function one(raw: LocationQuery, key: string): string | undefined {
  const value = raw[key];
  return typeof value === "string" ? value : undefined;
}

export function queryFromRoute(raw: LocationQuery): QueryState {
  const page = Number(one(raw, "page"));
  return {
    q: one(raw, "q") ?? DEFAULTS.q,
    min_price: one(raw, "min_price") ?? DEFAULTS.min_price,
    max_price: one(raw, "max_price") ?? DEFAULTS.max_price,
    city: one(raw, "city") ?? DEFAULTS.city,
    socket: one(raw, "socket") ?? DEFAULTS.socket,
    source: one(raw, "source") ?? DEFAULTS.source,
    potential: one(raw, "potential") ?? DEFAULTS.potential,
    kind: one(raw, "kind") ?? DEFAULTS.kind,
    sort: one(raw, "sort") ?? DEFAULTS.sort,
    page: Number.isFinite(page) && page >= 1 ? Math.floor(page) : DEFAULTS.page,
  };
}

export function queryToRoute(state: QueryState): Record<string, string> {
  const out: Record<string, string> = {};
  for (const key of Object.keys(DEFAULTS) as (keyof QueryState)[]) {
    const value = String(state[key]);
    if (value !== "" && value !== String(DEFAULTS[key])) out[key] = value;
  }
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
      const next = queryToRoute(query);
      if (fingerprint(queryFromRoute(route.query)) === fingerprint(query)) return;
      router.replace({ query: next });
    },
    { deep: true },
  );

  return query;
}
