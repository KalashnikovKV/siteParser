"""Поиск и карточка для UI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from skelbiu_pc.db.connection import connect
from skelbiu_pc.db.fts import fts_match_query
from skelbiu_pc.db.schema import NO_TEXT_SQL, NOT_LAPTOP_SQL, STALE_DETAIL_SQL
from skelbiu_pc.urls import safe_http_url


def _parts_brief(parts: dict | None) -> dict:
    parts = parts or {}
    return {
        "cpu": parts.get("cpu"),
        "gpu": parts.get("gpu"),
        "ram": parts.get("ram"),
        "ram_gb": parts.get("ram_gb"),
        "motherboard": parts.get("motherboard"),
        "chipset": parts.get("chipset"),
        "socket": parts.get("socket"),
        "psu": parts.get("psu"),
        "storage": parts.get("storage"),
        "is_desktop": parts.get("is_desktop"),
        "is_laptop": parts.get("is_laptop"),
    }


def _listing_row(row: sqlite3.Row, parts_json: str | None, include_analysis: bool = False) -> dict:
    item = dict(row)
    item["url"] = safe_http_url(item.get("url"))
    parts = json.loads(parts_json) if parts_json else {}
    analysis = None
    payload = item.pop("payload_json", None)
    if payload:
        analysis = json.loads(payload)
    item["price_eur"] = (item["price_cents"] / 100) if item.get("price_cents") is not None else None
    item["parts"] = _parts_brief(parts) if not include_analysis else parts
    item["analysis"] = analysis
    plan = (analysis or {}).get("plan") or {}
    item["upgrade_cost_eur"] = item.get("upgrade_cost_eur", plan.get("upgrade_cost_eur"))
    item["resale_eur"] = item.get("resale_eur", plan.get("resale_eur"))
    item["profit_eur"] = item.get("profit_eur", plan.get("profit_eur"))
    item["has_description"] = bool(item.get("has_description"))
    item["has_potential"] = bool(item.get("has_potential"))
    item["is_desktop"] = bool(item.get("is_desktop"))
    item["is_active"] = bool(item.get("is_active", 1))
    item["source"] = item.get("source") or "skelbiu"
    flags_raw = item.pop("ai_flags_json", None)
    payload_ai = item.pop("ai_payload_json", None)
    action = item.pop("ai_action", None)
    interest = item.pop("ai_interest", None)
    summary = item.pop("ai_summary", None)
    model = item.pop("ai_model", None)
    if payload_ai:
        item["advice"] = json.loads(payload_ai)
    elif action or interest is not None:
        item["advice"] = {
            "action": action,
            "interest": interest,
            "summary": summary,
            "flags": json.loads(flags_raw) if flags_raw else [],
            "model": model,
        }
    else:
        item["advice"] = None
    return item


PRESETS: dict[str, dict] = {
    "picks": {
        "advice": "buy,inspect",
        "potential": True,
        "sort": "ai",
        "has_description": True,
    },
    "upgrade": {
        "potential": True,
        "sort": "score",
        "min_score": 40,
    },
    "cheap": {
        "potential": True,
        "max_price_eur": 250,
        "sort": "price_asc",
    },
    "margin": {
        "potential": True,
        "min_profit_eur": 40,
        "sort": "profit",
    },
    "fresh": {
        "sort": "seen",
    },
}


def search_listings(
    *,
    q: str | None = None,
    min_price_eur: float | None = None,
    max_price_eur: float | None = None,
    city: str | None = None,
    socket: str | None = None,
    source: str | None = None,
    potential: bool | None = None,
    advice: str | None = None,
    min_score: float | None = None,
    min_profit_eur: float | None = None,
    has_description: bool | None = None,
    preset: str | None = None,
    kind: str = "all",
    sort: str = "score",
    page: int = 1,
    limit: int = 30,
    active_only: bool = True,
    path: Path | None = None,
) -> dict:
    if preset and preset in PRESETS:
        bundle = PRESETS[preset]
        potential = bundle.get("potential", potential)
        advice = bundle.get("advice", advice)
        min_score = bundle.get("min_score", min_score)
        min_profit_eur = bundle.get("min_profit_eur", min_profit_eur)
        max_price_eur = bundle.get("max_price_eur", max_price_eur)
        has_description = bundle.get("has_description", has_description)
        sort = bundle.get("sort", sort)

    where = ["1=1"]
    params: list = []
    if active_only:
        where.append("l.is_active = 1")
    if q:
        match = fts_match_query(q)
        if match:
            where.append(
                "l.id IN (SELECT listing_id FROM listings_fts WHERE listings_fts MATCH ?)"
            )
            params.append(match)
        else:
            like = f"%{q.strip()}%"
            where.append("(l.title LIKE ? OR ifnull(l.description, '') LIKE ?)")
            params.extend([like, like])
    if min_price_eur is not None:
        where.append("l.price_cents >= ?")
        params.append(int(min_price_eur * 100))
    if max_price_eur is not None:
        where.append("l.price_cents <= ?")
        params.append(int(max_price_eur * 100))
    if city:
        where.append("l.city = ?")
        params.append(city)
    if socket:
        where.append("a.socket = ?")
        params.append(socket)
    if source:
        where.append("ifnull(l.source, 'skelbiu') = ?")
        params.append(source)
    if potential is True:
        where.append("a.has_potential = 1")
    elif potential is False:
        where.append("(a.has_potential = 0 OR a.has_potential IS NULL)")
    if advice:
        actions = [part.strip().lower() for part in advice.split(",") if part.strip()]
        if actions == ["any"]:
            where.append("v.listing_id IS NOT NULL")
        elif actions:
            placeholders = ",".join("?" * len(actions))
            where.append(f"v.action IN ({placeholders})")
            params.extend(actions)
    if min_score is not None:
        where.append("a.score >= ?")
        params.append(min_score)
    if min_profit_eur is not None:
        where.append("a.profit_eur >= ?")
        params.append(min_profit_eur)
    if has_description is True:
        where.append("l.description IS NOT NULL AND l.description != ''")
    elif has_description is False:
        where.append("(l.description IS NULL OR l.description = '')")
    if kind == "laptop":
        where.append("1 = 0")
    else:
        where.append(NOT_LAPTOP_SQL)

    order = {
        "score": "a.score IS NULL, a.score DESC, l.last_seen_at DESC",
        "price_asc": "l.price_cents IS NULL, l.price_cents ASC",
        "price_desc": "l.price_cents IS NULL, l.price_cents DESC",
        "seen": "l.last_seen_at DESC",
        "title": "l.title COLLATE NOCASE",
        "profit": "a.profit_eur IS NULL, a.profit_eur DESC",
        "resale": "a.resale_eur IS NULL, a.resale_eur DESC",
        "cost": "a.upgrade_cost_eur IS NULL, a.upgrade_cost_eur ASC",
        "ai": (
            "CASE v.action WHEN 'buy' THEN 0 WHEN 'inspect' THEN 1 "
            "WHEN 'skip' THEN 2 ELSE 3 END, "
            "v.interest IS NULL, v.interest DESC, a.score DESC"
        ),
    }.get(sort, "a.score IS NULL, a.score DESC")

    where_sql = " AND ".join(where)
    base = f"""
        FROM listings l
        LEFT JOIN analyses a ON a.listing_id = l.id
        LEFT JOIN parts p ON p.listing_id = l.id
        LEFT JOIN advice v ON v.listing_id = l.id
        WHERE {where_sql}
    """
    page = max(1, page)
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit

    with connect(path) as conn:
        total = conn.execute(f"SELECT count(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT l.id, l.url, l.title, l.price_cents, l.city, l.condition,
                   l.is_desktop, l.is_active, l.last_seen_at,
                   ifnull(l.source, 'skelbiu') AS source,
                   (l.description IS NOT NULL AND l.description != '') AS has_description,
                   a.score, a.verdict, a.socket, a.has_potential, a.payload_json,
                   a.upgrade_cost_eur, a.resale_eur, a.profit_eur,
                   v.action AS ai_action, v.interest AS ai_interest,
                   v.summary AS ai_summary, v.flags_json AS ai_flags_json,
                   v.model AS ai_model,
                   p.payload_json AS parts_json
            {base}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = []
    for row in rows:
        data = dict(row)
        parts_json = data.pop("parts_json")
        items.append(_listing_row(data, parts_json))
    return {"items": items, "total": total, "page": page, "limit": limit}


def get_listing(listing_id: str, path: Path | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            """
            SELECT l.id, l.url, l.title, l.price_cents, l.city, l.condition,
                   l.description, l.attributes_json, l.is_desktop, l.is_active,
                   ifnull(l.source, 'skelbiu') AS source,
                   l.first_seen_at, l.last_seen_at, l.last_detail_at,
                   (l.description IS NOT NULL AND l.description != '') AS has_description,
                   a.score, a.verdict, a.socket, a.has_potential, a.payload_json,
                   a.upgrade_cost_eur, a.resale_eur, a.profit_eur,
                   v.action AS ai_action, v.interest AS ai_interest,
                   v.summary AS ai_summary, v.flags_json AS ai_flags_json,
                   v.model AS ai_model, v.payload_json AS ai_payload_json,
                   p.payload_json AS parts_json
            FROM listings l
            LEFT JOIN analyses a ON a.listing_id = l.id
            LEFT JOIN parts p ON p.listing_id = l.id
            LEFT JOIN advice v ON v.listing_id = l.id
            WHERE l.id = ?
            """,
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        parts_json = data.pop("parts_json")
        attributes_raw = data.pop("attributes_json")
        item = _listing_row(data, parts_json, include_analysis=True)
        item["description"] = data.get("description")
        item["attributes"] = json.loads(attributes_raw) if attributes_raw else {}
        item["price_points"] = price_series(listing_id, path)
        item["first_seen_at"] = data.get("first_seen_at")
        item["last_seen_at"] = data.get("last_seen_at")
        item["last_detail_at"] = data.get("last_detail_at")
        return item


def stats(path: Path | None = None) -> dict:
    from skelbiu_pc.config import DETAIL_TTL_DAYS

    with connect(path) as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM listings) AS total,
              (SELECT count(*) FROM listings WHERE is_active = 1) AS active,
              (SELECT count(*) FROM listings
                WHERE description IS NOT NULL AND description != '') AS with_details,
              (SELECT count(*) FROM analyses) AS analyzed,
              (SELECT count(*) FROM analyses a
                JOIN listings l ON l.id = a.listing_id
                WHERE l.is_active = 1 AND a.has_potential = 1) AS with_potential,
              (SELECT count(*) FROM advice) AS advised
            """
        ).fetchone()
        # То же множество, что «Все» в UI и очередь «Докачать описания».
        sale = conn.execute(
            f"""
            SELECT count(*) AS on_sale,
                   ifnull(sum({NO_TEXT_SQL}), 0) AS missing,
                   ifnull(sum(NOT {NO_TEXT_SQL} AND {STALE_DETAIL_SQL}), 0) AS stale
            FROM listings l
            LEFT JOIN parts p ON p.listing_id = l.id
            WHERE l.is_active = 1 AND {NOT_LAPTOP_SQL}
            """,
            (f"-{DETAIL_TTL_DAYS} days",),
        ).fetchone()
        run = conn.execute(
            """
            SELECT started_at, finished_at, list_url, listings_seen, new_listings
            FROM scrape_runs ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    return {
        "total": row["total"],
        "active": row["active"],
        "with_details": row["with_details"],
        "analyzed": row["analyzed"],
        "with_potential": row["with_potential"],
        "advised": row["advised"],
        "on_sale": sale["on_sale"],
        "details_missing": sale["missing"],
        "details_stale": sale["stale"],
        "details_fresh": sale["on_sale"] - sale["missing"] - sale["stale"],
        "unanalyzed": max(0, row["total"] - row["analyzed"]),
        "detail_ttl_days": DETAIL_TTL_DAYS,
        "last_run": dict(run) if run else None,
    }


def filter_options(path: Path | None = None) -> dict:
    with connect(path) as conn:
        cities = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT city FROM listings WHERE city IS NOT NULL AND city != '' ORDER BY city"
            )
        ]
        sockets = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT socket FROM analyses WHERE socket IS NOT NULL ORDER BY socket"
            )
        ]
        sources = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT ifnull(source, 'skelbiu') FROM listings ORDER BY 1"
            )
        ]
        advice_rows = conn.execute(
            f"""
            SELECT v.action, count(*) AS n
            FROM advice v
            JOIN listings l ON l.id = v.listing_id
            LEFT JOIN parts p ON p.listing_id = l.id
            WHERE l.is_active = 1 AND {NOT_LAPTOP_SQL}
            GROUP BY v.action
            ORDER BY n DESC
            """
        ).fetchall()
        advice_counts = {row["action"]: row["n"] for row in advice_rows}
    return {
        "cities": cities,
        "sockets": sockets,
        "sources": sources,
        "advice_counts": advice_counts,
        "presets": list(PRESETS),
    }


def top_picks(limit: int = 8, path: Path | None = None) -> dict:
    """Лучшие лоты по мнению модели: сначала «брать», потом «смотреть»."""
    advised = search_listings(
        advice="buy,inspect",
        potential=True,
        has_description=True,
        sort="ai",
        page=1,
        limit=limit,
        path=path,
    )
    if advised["total"] > 0:
        return {
            "items": advised["items"],
            "total": advised["total"],
            "source": "advice",
            "title": "Рекомендации модели",
        }
    fallback = search_listings(
        potential=True,
        min_score=40,
        sort="profit",
        page=1,
        limit=limit,
        path=path,
    )
    return {
        "items": fallback["items"],
        "total": fallback["total"],
        "source": "rules",
        "title": "Лучшие по правилам (модель ещё не смотрела)",
    }


def price_series(listing_id: str, path: Path | None = None) -> list[dict]:
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT price_cents, seen_at
            FROM price_history
            WHERE listing_id = ?
            ORDER BY seen_at
            """,
            (listing_id,),
        ).fetchall()
        return [dict(r) for r in rows]
