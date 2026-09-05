/** Презентеры: одно место для денег, оценки и тона маржи. */

export function formatEur(value: number | null | undefined): string {
  return value == null ? "—" : `${Number(value).toFixed(0)} €`;
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
  return ACTION_LABEL[action] || action;
}

export function adviceClass(action: string | null | undefined): string {
  if (action === "buy") return "badge good";
  if (action === "inspect") return "badge mid";
  if (action === "skip") return "badge bad";
  return "badge";
}
