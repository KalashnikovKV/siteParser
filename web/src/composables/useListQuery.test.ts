import { describe, expect, it } from "vitest";
import type { QueryState } from "../types";
import { ALL_LISTINGS, DEFAULTS, HOME_QUERY, queryFromRoute, queryToRoute } from "./useListQuery";

describe("queryFromRoute", () => {
  it("пустой URL — домашний «Топ модели»", () => {
    expect(queryFromRoute({})).toEqual(HOME_QUERY);
    expect(queryFromRoute({}).preset).toBe("picks");
  });

  it("фильтры из ссылки не подменяются пресетом", () => {
    const state = queryFromRoute({ max_price: "300", sort: "seen" });
    expect(state.preset).toBe("");
    expect(state.max_price).toBe("300");
    expect(state.sort).toBe("seen");
  });

  it("view=all сильнее preset", () => {
    expect(queryFromRoute({ view: "all" }).preset).toBe("");
    expect(queryFromRoute({ view: "all", preset: "cheap" }).preset).toBe("");
    expect(queryFromRoute({ preset: "cheap" }).preset).toBe("cheap");
  });

  it.each([
    ["3", 3],
    ["2.7", 2],
    ["0", 1],
    ["-4", 1],
    ["abc", 1],
    ["Infinity", 1],
    ["", 1],
  ])("страница %s → %i", (raw, page) => {
    expect(queryFromRoute({ page: raw }).page).toBe(page);
  });

  it("повторённый параметр не превращается в массив в состоянии", () => {
    const state = queryFromRoute({ q: ["ryzen", "intel"], city: ["Vilnius"] });
    expect(state.q).toBe("");
    expect(state.city).toBe("");
  });

  it("незнакомые параметры игнорируются", () => {
    const state = queryFromRoute({ utm_source: "x", sort: "profit" });
    expect(state).toEqual({ ...DEFAULTS, sort: "profit" });
  });
});

describe("queryToRoute", () => {
  it("домашнее состояние — чистый URL", () => {
    expect(queryToRoute(HOME_QUERY)).toEqual({});
  });

  it("каталог без категории помечается view=all", () => {
    expect(queryToRoute(ALL_LISTINGS)).toEqual({ view: "all" });
  });

  it("пишет только отличия от умолчаний", () => {
    expect(queryToRoute({ ...ALL_LISTINGS, max_price: "300", sort: "seen", page: 2 })).toEqual({
      max_price: "300",
      sort: "seen",
      page: "2",
      view: "all",
    });
  });

  const reachable: [string, QueryState][] = [
    ["дом", HOME_QUERY],
    ["все", ALL_LISTINGS],
    ["пресет", { ...DEFAULTS, preset: "cheap" }],
    ["пресет, стр. 3", { ...DEFAULTS, preset: "margin", page: 3 }],
    ["топ с другой сортировкой", { ...HOME_QUERY, sort: "score" }],
    ["цена и сортировка", { ...ALL_LISTINGS, max_price: "300", sort: "seen" }],
    [
      "все фильтры",
      {
        ...ALL_LISTINGS,
        q: "ryzen b550",
        min_price: "50",
        max_price: "400",
        city: "Vilnius",
        socket: "AM4",
        source: "skelbiu",
        potential: "true",
        advice: "buy",
        min_score: "40",
        min_profit: "-20",
        has_description: "false",
        kind: "all",
        sort: "price_asc",
        page: 4,
      },
    ],
  ];

  it.each(reachable)("состояние «%s» переживает URL", (_name, state) => {
    expect(queryFromRoute(queryToRoute(state))).toEqual(state);
  });
});
