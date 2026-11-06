import { describe, expect, it } from "vitest";
import {
  adviceClass,
  adviceLabel,
  flagLabel,
  formatDateTime,
  formatEur,
  formatInt,
  formatScore,
  isWarningFlag,
  labelFrom,
  profitTone,
  safeExternalUrl,
  scoreClass,
  scoreTone,
} from "./format";

/** Intl ставит неразрывные пробелы между разрядами — сравниваем по смыслу. */
const plain = (text: string) => text.replace(/\s/g, " ");

describe("числа и даты", () => {
  it("форматирует евро с разрядами и округлением", () => {
    expect(plain(formatEur(1234.6))).toBe("1 235 €");
    expect(formatEur(0)).toBe("0 €");
    expect(plain(formatEur(-606))).toBe("-606 €");
  });

  it("показывает прочерк вместо пустых значений", () => {
    for (const fn of [formatEur, formatInt, formatScore]) {
      expect(fn(null)).toBe("—");
      expect(fn(undefined)).toBe("—");
    }
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("")).toBe("—");
    expect(formatDateTime("не дата")).toBe("—");
  });

  it("округляет оценку до целого", () => {
    expect(formatScore(62.6)).toBe("63");
    expect(plain(formatInt(7651))).toBe("7 651");
  });

  it("форматирует дату по-русски", () => {
    expect(formatDateTime("2026-09-05T14:49:20+00:00")).toMatch(/сент/);
  });
});

describe("safeExternalUrl", () => {
  it("пропускает только http(s)", () => {
    expect(safeExternalUrl("https://ru.skelbiu.lt/skelbimai/pc-1.html")).toBe(
      "https://ru.skelbiu.lt/skelbimai/pc-1.html",
    );
    expect(safeExternalUrl("http://example.com/a")).toBe("http://example.com/a");
  });

  it.each([
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "https://user:pw@skelbiu.lt/",
    "//evil.example/x",
    "/relative/path",
    "не ссылка",
    "",
    null,
    undefined,
  ])("отбрасывает %s", (url) => {
    expect(safeExternalUrl(url)).toBeNull();
  });
});

describe("тона и подписи", () => {
  it("красит оценку по порогам правил", () => {
    expect(scoreTone(55)).toBe("good");
    expect(scoreTone(54.9)).toBe("mid");
    expect(scoreTone(40)).toBe("mid");
    expect(scoreTone(39.9)).toBe("bad");
    expect(scoreTone(null)).toBe("");
    expect(scoreClass(70)).toBe("badge good");
    expect(scoreClass(undefined)).toBe("badge");
  });

  it("красит маржу", () => {
    expect(profitTone(40)).toBe("good");
    expect(profitTone(39)).toBe("");
    expect(profitTone(0)).toBe("");
    expect(profitTone(-1)).toBe("bad");
    expect(profitTone(null)).toBe("muted");
  });

  it("переводит совет модели", () => {
    expect(adviceLabel("buy")).toBe("брать");
    expect(adviceLabel("inspect")).toBe("смотреть");
    expect(adviceLabel("skip")).toBe("пропуск");
    expect(adviceLabel("maybe")).toBe("maybe");
    expect(adviceLabel(null)).toBe("—");
    expect(adviceClass("buy")).toBe("badge good");
    expect(adviceClass("inspect")).toBe("badge mid");
    expect(adviceClass("skip")).toBe("badge bad");
    expect(adviceClass("maybe")).toBe("badge");
  });

  it("не достаёт из словаря методы Object", () => {
    const table = { picks: "Топ модели" };
    expect(labelFrom(table, "picks")).toBe("Топ модели");
    for (const key of ["constructor", "toString", "__proto__", "hasOwnProperty"]) {
      expect(labelFrom(table, key)).toBe(key);
      expect(flagLabel(key)).toBe(key);
      expect(adviceLabel(key)).toBe(key);
    }
  });

  it("выделяет флаги защиты", () => {
    expect(flagLabel("prompt_injection")).toBe("текст пытается командовать моделью");
    expect(isWarningFlag("prompt_injection")).toBe(true);
    expect(isWarningFlag("parse_error")).toBe(true);
    expect(flagLabel("высокая цена")).toBe("высокая цена");
    expect(isWarningFlag("высокая цена")).toBe(false);
    expect(isWarningFlag("toString")).toBe(false);
  });
});
