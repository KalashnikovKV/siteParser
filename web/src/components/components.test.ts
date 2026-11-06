import { describe, expect, it } from "vitest";
import { createSSRApp, type Component } from "vue";
import { renderToString } from "vue/server-renderer";
import type { JobStatus, PricePoint } from "../types";
import JobButton from "./JobButton.vue";
import PriceChart from "./PriceChart.vue";

function render(component: Component, props: Record<string, unknown>) {
  return renderToString(createSSRApp(component, props));
}

const plain = (html: string) => html.replace(/\s+/g, " ");

function job(done: number, total: number): JobStatus {
  return { running: true, kind: "details", done, total, analyzed: done, error: null, stats: null };
}

describe("JobButton", () => {
  const base = { label: "Докачать описания", busyLabel: "Описания", hint: "подсказка" };

  it("в покое — обычная кнопка", async () => {
    const html = await render(JobButton, { ...base, busy: false, job: null });
    expect(html).toContain("Докачать описания");
    expect(html).not.toContain("disabled");
    expect(html).not.toContain("<progress");
    expect(html).toContain('title="подсказка"');
  });

  it("пока сервер не знает объём — неопределённый прогресс", async () => {
    const html = await render(JobButton, { ...base, busy: true, job: job(0, 0) });
    expect(html).toContain("Описания");
    expect(html).toContain("disabled");
    expect(html).toContain('aria-busy="true"');
    expect(html).toMatch(/<progress(?![^>]*\svalue=)[^>]*>/);
    expect(html).not.toContain("job-counter");
  });

  it("с объёмом — счётчик и прогресс", async () => {
    const html = await render(JobButton, { ...base, busy: true, job: job(37, 200) });
    expect(html).toContain("37/200");
    expect(html).toMatch(/<progress[^>]*max="200"[^>]*value="37"|<progress[^>]*value="37"[^>]*max="200"/);
  });
});

describe("PriceChart", () => {
  const at = (day: number) => `2026-09-${String(day).padStart(2, "0")}T12:00:00+00:00`;
  const points = (...prices: (number | null)[]): PricePoint[] =>
    prices.map((price_cents, i) => ({ price_cents, seen_at: at(i + 1) }));

  it("одна точка — без графика", async () => {
    const html = await render(PriceChart, { points: points(15000) });
    expect(html).not.toContain("<svg");
    expect(html).toContain("история ещё копится");
  });

  it("рост цены с разрядами и минимумом/максимумом", async () => {
    const html = plain(await render(PriceChart, { points: points(100000, null, 250000) }));
    expect(html).toContain("<svg");
    expect(html).toMatch(/\+1\s500 € с первого захода/);
    expect(html).toMatch(/мин 1\s000 €/);
    expect(html).toMatch(/макс 2\s500 €/);
  });

  it("падение цены — со знаком минус", async () => {
    const html = plain(await render(PriceChart, { points: points(22000, 18000) }));
    expect(html).toContain("−40 € с первого захода");
  });

  it("ровная цена не ломает масштаб", async () => {
    const html = await render(PriceChart, { points: points(9000, 9000) });
    expect(html).toContain("без изменения с первого захода");
    expect(html).not.toContain("NaN");
  });
});
