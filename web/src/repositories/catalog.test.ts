import { describe, expect, it, vi } from "vitest";
import { catalog } from "./catalog";

function reply(status: number, body: unknown, contentType = "application/json") {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return new Response(text, { status, headers: { "Content-Type": contentType } });
}

function stubFetch(...responses: (Response | Error)[]) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => {
    const next = responses.shift() ?? reply(200, {});
    if (next instanceof Error) throw next;
    return next;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function headersOf(init: RequestInit | undefined): Headers {
  return new Headers(init?.headers);
}

describe("запросы", () => {
  it("POST несёт CSRF-заголовок", async () => {
    const fetchMock = stubFetch(reply(200, { running: true }), reply(200, { running: true }));
    await catalog.analyze();
    await catalog.details();
    for (const [url, init] of fetchMock.mock.calls) {
      expect(init?.method).toBe("POST");
      expect(headersOf(init).get("X-Skelbiu-Request")).toBe("1");
      expect(init?.credentials).toBe("same-origin");
      expect(url).toMatch(/^\/api\/(analyze|details)$/);
    }
  });

  it("GET без лишних заголовков и с cookie/логином только своего сайта", async () => {
    const fetchMock = stubFetch(reply(200, { total: 1 }));
    await catalog.stats();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/stats");
    expect(init?.method).toBeUndefined();
    expect(init?.credentials).toBe("same-origin");
  });

  it("номер объявления кодируется в пути", async () => {
    const fetchMock = stubFetch(reply(200, {}), reply(200, {}));
    await catalog.listing("../stats?x=1#y");
    await catalog.adviseListing("a/b");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/listings/..%2Fstats%3Fx%3D1%23y");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/listings/a%2Fb/advise");
    expect(headersOf(fetchMock.mock.calls[1][1]).get("X-Skelbiu-Request")).toBe("1");
  });

  it("listings пропускает пустые параметры и передаёт signal", async () => {
    const fetchMock = stubFetch(reply(200, { items: [], total: 0 }));
    const controller = new AbortController();
    await catalog.listings(
      { q: "rtx 3060&x=1", city: "", socket: undefined, page: 2, limit: 30 },
      { signal: controller.signal },
    );
    const [url, init] = fetchMock.mock.calls[0];
    const params = new URL(url, "http://localhost").searchParams;
    expect(params.get("q")).toBe("rtx 3060&x=1");
    expect(params.has("city")).toBe(false);
    expect(params.has("socket")).toBe(false);
    expect(params.get("page")).toBe("2");
    expect(init?.signal).toBe(controller.signal);
  });

  it("adviseJob отдаёт пустую задачу, если сервер её не прислал", async () => {
    stubFetch(reply(200, { available: false, backend: "off", model: null, error: "выключен" }));
    await expect(catalog.adviseJob()).resolves.toMatchObject({ running: false, total: 0 });
  });
});

describe("ошибки понятны человеку", () => {
  it("строковый detail показывается как есть", async () => {
    stubFetch(reply(404, { detail: "Объявление не найдено" }));
    await expect(catalog.listing("1")).rejects.toThrow("Объявление не найдено");
  });

  it("422 называет поле по-русски", async () => {
    stubFetch(
      reply(422, {
        detail: [{ loc: ["path", "listing_id"], msg: "String should match pattern" }],
      }),
    );
    await expect(catalog.listing("x")).rejects.toThrow("Недопустимое значение: номер объявления");
  });

  it("422 по нескольким полям — без повторов", async () => {
    stubFetch(
      reply(422, {
        detail: [
          { loc: ["query", "min_price"] },
          { loc: ["query", "min_price"] },
          { loc: ["query", "max_price"] },
          { loc: ["query", "constructor"] },
        ],
      }),
    );
    await expect(catalog.listings({ min_price: "nan" })).rejects.toThrow(
      "Недопустимое значение: цена от, цена до, constructor",
    );
  });

  it.each([
    [401, "Нужен логин и пароль — обнови страницу"],
    [403, "Сервер отклонил запрос"],
    [500, "Ошибка сервера (500)"],
    [502, "Ошибка сервера (502)"],
  ])("статус %i без JSON", async (status, text) => {
    stubFetch(reply(status, "<html>oops</html>", "text/html"));
    await expect(catalog.stats()).rejects.toThrow(text);
  });

  it("сеть недоступна", async () => {
    stubFetch(new TypeError("Failed to fetch"));
    await expect(catalog.stats()).rejects.toThrow("Нет связи с сервером");
  });
});
