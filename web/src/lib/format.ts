/** Презентеры: одно место для денег, оценки и тона маржи. */

/** Подпись из словаря. Ключ приходит из URL или от модели: «constructor» не должен достать метод Object. */
export function labelFrom(table: Record<string, string>, key: string): string {
  return Object.hasOwn(table, key) ? table[key] : key;
}

const intFormat = new Intl.NumberFormat("ru-RU");
const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatEur(value: number | null | undefined): string {
  return value == null ? "—" : `${intFormat.format(Math.round(Number(value)))} €`;
}

export function formatInt(value: number | null | undefined): string {
  return value == null ? "—" : intFormat.format(value);
}

export function formatScore(value: number | null | undefined): string {
  return value == null ? "—" : Number(value).toFixed(0);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
}

/** Ссылка наружу только по http(s): javascript:/data: из базы не превращаются в кликабельные. */
export function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    if (parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

export function scoreTone(score: number | null | undefined): "good" | "mid" | "bad" | "" {
  if (score == null) return "";
  if (score >= 55) return "good";
  if (score >= 40) return "mid";
  return "bad";
}

export function scoreClass(score: number | null | undefined): string {
  const tone = scoreTone(score);
  return tone ? `badge ${tone}` : "badge";
}

export function profitTone(value: number | null | undefined): "good" | "bad" | "muted" | "" {
  if (value == null) return "muted";
  if (value >= 40) return "good";
  if (value < 0) return "bad";
  return "";
}

const ACTION_LABEL: Record<string, string> = {
  buy: "брать",
  inspect: "смотреть",
  skip: "пропуск",
};

export function adviceLabel(action: string | null | undefined): string {
  if (!action) return "—";
  return labelFrom(ACTION_LABEL, action);
}

export function adviceClass(action: string | null | undefined): string {
  if (action === "buy") return "badge good";
  if (action === "inspect") return "badge mid";
  if (action === "skip") return "badge bad";
  return "badge";
}

const FLAG_LABEL: Record<string, string> = {
  prompt_injection: "текст пытается командовать моделью",
  parse_error: "модель ответила не по формату",
};

export function flagLabel(flag: string): string {
  return labelFrom(FLAG_LABEL, flag);
}

export function isWarningFlag(flag: string): boolean {
  return Object.hasOwn(FLAG_LABEL, flag);
}
