"""Отчёт по кандидатам и простой текстовый график цен."""

from __future__ import annotations

import json
from pathlib import Path

from skelbiu_pc.config import REPORTS_DIR


def format_top(rows: list[dict]) -> str:
    if not rows:
        return "Подходящих объявлений нет. Сначала fetch + analyze, затем опустите порог --min-score."

    lines = [
        "Кандидаты на апгрейд (материнская плата = потолок платформы)",
        "=" * 78,
    ]
    for i, row in enumerate(rows, 1):
        price = _eur(row.get("price_cents"))
        parts = row.get("parts") or {}
        analysis = row.get("analysis") or {}
        trend = sparkline(row.get("price_points") or [])
        delta = price_delta(row.get("price_points") or [])
        lines.append(
            f"\n{i}. [{analysis.get('score', row.get('score')):.1f}] "
            f"{row.get('title') or row['id']}"
        )
        lines.append(f"   {price}  {row.get('city') or ''}  {row.get('verdict') or analysis.get('verdict')}")
        lines.append(
            f"   сокет {row.get('socket') or '—'} | "
            f"CPU {parts.get('cpu') or '—'} | "
            f"GPU {parts.get('gpu') or 'нет'} | "
            f"RAM {parts.get('ram') or '—'} | "
            f"плата {parts.get('motherboard') or parts.get('chipset') or '—'}"
        )
        if trend:
            lines.append(f"   цена: {trend} {delta}")
        for reason in (analysis.get("reasons") or [])[:3]:
            lines.append(f"   • {reason}")
        upgrades = analysis.get("upgrades") or []
        if upgrades:
            lines.append("   апгрейд: " + "; ".join(upgrades[:4]))
        lines.append(f"   {row.get('url')}")
    return "\n".join(lines)


def sparkline(points: list[dict]) -> str:
    values = [p["price_cents"] for p in points if p.get("price_cents") is not None]
    if len(values) < 2:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if lo == hi:
        return chars[0] * len(values)
    out = []
    for v in values[-16:]:
        idx = int((v - lo) / (hi - lo) * (len(chars) - 1))
        out.append(chars[idx])
    return "".join(out)


def price_delta(points: list[dict]) -> str:
    values = [p["price_cents"] for p in points if p.get("price_cents") is not None]
    if len(values) < 2:
        return "история ещё копится"
    first, last = values[0], values[-1]
    diff = (last - first) / 100
    if diff == 0:
        return "без изменения с первого захода"
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.0f}€ с первого захода"


def write_json(rows: list[dict], path: Path | None = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = path or (REPORTS_DIR / "upgrade_candidates.json")
    payload = []
    for row in rows:
        item = dict(row)
        item["price_eur"] = (row.get("price_cents") or 0) / 100 if row.get("price_cents") else None
        payload.append(item)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def format_history(listing_id: str, title: str | None, points: list[dict]) -> str:
    lines = [f"История цены #{listing_id}", title or "", ""]
    if not points:
        return f"По объявлению {listing_id} истории ещё нет."
    for point in points:
        price = _eur(point.get("price_cents"))
        lines.append(f"  {point['seen_at']}   {price}")
    trend = sparkline(points)
    if trend:
        lines.append(f"\n  {trend}  {price_delta(points)}")
    return "\n".join(lines)


def _eur(cents: int | None) -> str:
    if cents is None:
        return "цена не указана"
    return f"{cents / 100:.0f} €"
