"""Запись объявлений, описаний, частей и оценок."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from skelbiu_pc.db.connection import connect, utcnow
from skelbiu_pc.db.fts import sync_fts
from skelbiu_pc.db.schema import NO_TEXT_SQL, NOT_LAPTOP_SQL, STALE_DETAIL_SQL
from skelbiu_pc.parts import guess_desktop, looks_like_laptop


def _plan_money(analysis: dict) -> tuple[float | None, float | None, float | None]:
    plan = analysis.get("plan") or {}
    return plan.get("upgrade_cost_eur"), plan.get("resale_eur"), plan.get("profit_eur")


def start_run(list_url: str, path: Path | None = None) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO scrape_runs (started_at, list_url) VALUES (?, ?)",
            (utcnow(), list_url),
        )
        return int(cur.lastrowid)


def finish_run(run_id: int, stats: dict, path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            UPDATE scrape_runs
            SET finished_at = ?, pages = ?, listings_seen = ?,
                new_listings = ?, price_changes = ?, details_fetched = ?
            WHERE id = ?
            """,
            (
                utcnow(),
                stats.get("pages", 0),
                stats.get("listings_seen", 0),
                stats.get("new_listings", 0),
                stats.get("price_changes", 0),
                stats.get("details_fetched", 0),
                run_id,
            ),
        )


def upsert_cards(cards: list[dict], path: Path | None = None) -> dict:
    stats = {"new": 0, "price_changed": 0, "seen": 0}
    with connect(path) as conn:
        for card in cards:
            result = _upsert_card_on(conn, card)
            stats["seen"] += 1
            stats["new"] += int(result["new"])
            stats["price_changed"] += int(result["price_changed"])
    return stats


def upsert_card(card: dict, path: Path | None = None) -> dict:
    with connect(path) as conn:
        return _upsert_card_on(conn, card)


def _upsert_card_on(conn: sqlite3.Connection, card: dict) -> dict:
    from skelbiu_pc.prices import resolve_listing_price

    now = utcnow()
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (card["id"],)).fetchone()
    title = card.get("title") or (row["title"] if row else None)
    description = row["description"] if row else None
    card_price = card.get("price_cents")
    price, _note = resolve_listing_price(card_price, title, description)
    result = {"new": False, "price_changed": False}

    laptop = looks_like_laptop(card.get("title"))
    desktop_flag = 0 if laptop else guess_desktop(card.get("title"))
    if row is None:
        conn.execute(
            """
            INSERT INTO listings (
                id, url, title, price_cents, card_price_cents, currency, city, condition,
                is_desktop, first_seen_at, last_seen_at, is_active, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card["id"],
                card["url"],
                card.get("title"),
                price,
                card_price,
                card.get("currency", "EUR"),
                card.get("city"),
                card.get("condition"),
                desktop_flag,
                now,
                now,
                0 if laptop else 1,
                card.get("source") or "skelbiu",
            ),
        )
        conn.execute(
            "INSERT INTO price_history (listing_id, price_cents, seen_at) VALUES (?, ?, ?)",
            (card["id"], price, now),
        )
        sync_fts(conn, card["id"])
        result["new"] = True
        return result

    last_price = row["price_cents"]
    conn.execute(
        """
        UPDATE listings
        SET url = ?, title = COALESCE(?, title),
            price_cents = ?, card_price_cents = ?, city = COALESCE(?, city),
            condition = COALESCE(?, condition),
            last_seen_at = ?,
            is_active = CASE WHEN ? THEN 0 ELSE 1 END,
            is_desktop = CASE WHEN ? THEN 0 ELSE is_desktop END,
            source = COALESCE(?, source)
        WHERE id = ?
        """,
        (
            card["url"],
            card.get("title"),
            price,
            card_price,
            card.get("city"),
            card.get("condition"),
            now,
            int(laptop),
            int(laptop),
            card.get("source"),
            card["id"],
        ),
    )
    if price is not None and price != last_price:
        conn.execute(
            "INSERT INTO price_history (listing_id, price_cents, seen_at) VALUES (?, ?, ?)",
            (card["id"], price, now),
        )
        result["price_changed"] = True
    sync_fts(conn, card["id"])
    return result


def mark_missing_inactive(seen_ids: set[str], path: Path | None = None) -> int:
    if not seen_ids:
        return 0
    with connect(path) as conn:
        placeholders = ",".join("?" * len(seen_ids))
        cur = conn.execute(
            f"UPDATE listings SET is_active = 0 WHERE id NOT IN ({placeholders}) AND is_active = 1",
            tuple(seen_ids),
        )
        return cur.rowcount


def apply_price(listing_id: str, price_cents: int, path: Path | None = None) -> bool:
    with connect(path) as conn:
        return _apply_price_on(conn, listing_id, price_cents)


def _apply_price_on(conn: sqlite3.Connection, listing_id: str, price_cents: int) -> bool:
    row = conn.execute(
        "SELECT price_cents FROM listings WHERE id = ?", (listing_id,)
    ).fetchone()
    if row is None or row["price_cents"] == price_cents:
        return False
    now = utcnow()
    conn.execute(
        "UPDATE listings SET price_cents = ? WHERE id = ?",
        (price_cents, listing_id),
    )
    conn.execute(
        "INSERT INTO price_history (listing_id, price_cents, seen_at) VALUES (?, ?, ?)",
        (listing_id, price_cents, now),
    )
    return True


def update_detail(detail: dict, path: Path | None = None) -> None:
    from skelbiu_pc.prices import resolve_listing_price

    description = (detail.get("description") or "").strip() or None
    attributes = detail.get("attributes") or {}
    with connect(path) as conn:
        row = conn.execute(
            "SELECT price_cents, card_price_cents, title, description FROM listings WHERE id = ?",
            (detail["id"],),
        ).fetchone()
        card_price = row["card_price_cents"] if row else None
        if card_price is None:
            card_price = (
                detail.get("price_cents")
                if detail.get("price_cents") is not None
                else (row["price_cents"] if row else None)
            )
        resolved, _note = resolve_listing_price(
            card_price,
            detail.get("title") or (row["title"] if row else None),
            description or (row["description"] if row else None),
        )
        conn.execute(
            """
            UPDATE listings
            SET title = COALESCE(?, title),
                price_cents = COALESCE(?, price_cents),
                city = COALESCE(?, city),
                condition = COALESCE(?, condition),
                description = COALESCE(?, description),
                attributes_json = CASE
                    WHEN ? != '{}' THEN ?
                    ELSE attributes_json
                END,
                last_detail_at = ?
            WHERE id = ?
            """,
            (
                detail.get("title"),
                resolved,
                detail.get("city"),
                detail.get("condition"),
                description,
                json.dumps(attributes, ensure_ascii=False),
                json.dumps(attributes, ensure_ascii=False),
                utcnow(),
                detail["id"],
            ),
        )
        old_price = row["price_cents"] if row else None
        if resolved is not None and old_price is not None and resolved != old_price:
            conn.execute(
                "INSERT INTO price_history (listing_id, price_cents, seen_at) VALUES (?, ?, ?)",
                (detail["id"], resolved, utcnow()),
            )
        sync_fts(conn, detail["id"])


def listings_needing_details(
    ttl_days: int,
    limit: int | None = None,
    path: Path | None = None,
    *,
    missing_only: bool = False,
    candidates_only: bool = True,
    min_score: float | None = None,
) -> list[dict]:
    from skelbiu_pc.config import DETAIL_MIN_SCORE

    score_floor = DETAIL_MIN_SCORE if min_score is None else min_score
    with connect(path) as conn:
        sql = """
            SELECT l.id, l.url, l.title, l.price_cents, l.last_detail_at, l.description,
                   ifnull(l.source, 'skelbiu') AS source
            FROM listings l
            LEFT JOIN analyses a ON a.listing_id = l.id
            LEFT JOIN parts p ON p.listing_id = l.id
            WHERE l.is_active = 1
        """
        params: list = []
        if missing_only:
            # Без last_detail_at или с пустым текстом (неудачный прошлый заход).
            sql += f" AND (l.last_detail_at IS NULL OR {NO_TEXT_SQL})"
        else:
            sql += f" AND ({NO_TEXT_SQL} OR {STALE_DETAIL_SQL})"
            params.append(f"-{ttl_days} days")
        sql += f" AND {NOT_LAPTOP_SQL}"
        if candidates_only:
            sql += """
              AND (
                    ifnull(a.score, 0) >= ?
                 OR a.listing_id IS NULL
              )
            """
            params.append(score_floor)
        # Сначала ни разу не открытые, потом пустые после сбоя, и только потом устаревшие:
        # иначе обновление старых текстов бесконечно оттесняет пустые.
        sql += f"""
            ORDER BY l.last_detail_at IS NOT NULL,
                     NOT {NO_TEXT_SQL},
                     ifnull(a.score, 0) DESC,
                     ifnull(l.is_desktop, 1) DESC
        """
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def update_kind(
    listing_id: str,
    is_desktop: bool,
    is_laptop: bool,
    path: Path | None = None,
) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            UPDATE listings
            SET is_desktop = ?,
                is_active = CASE WHEN ? THEN 0 ELSE is_active END
            WHERE id = ?
            """,
            (1 if is_desktop and not is_laptop else 0, 1 if is_laptop else 0, listing_id),
        )


def analyzed_ids(path: Path | None = None) -> set[str]:
    with connect(path) as conn:
        rows = conn.execute("SELECT listing_id FROM analyses").fetchall()
        return {r[0] for r in rows}


def listing_for_analyze(listing_id: str, path: Path | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            """
            SELECT id, title, price_cents, description, attributes_json
            FROM listings WHERE id = ?
            """,
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        raw = item.pop("attributes_json")
        item["attributes"] = json.loads(raw) if raw else {}
        return item


def iter_listings(active_only: bool = True, path: Path | None = None):
    sql = """
        SELECT id, url, title, price_cents, card_price_cents, city, condition,
               description, attributes_json, is_desktop, is_active
        FROM listings
    """
    if active_only:
        sql += " WHERE is_active = 1"
    with connect(path) as conn:
        rows = conn.execute(sql).fetchall()
        for row in rows:
            item = dict(row)
            raw = item.get("attributes_json")
            item["attributes"] = json.loads(raw) if raw else {}
            yield item


def iter_active_listings(path: Path | None = None):
    yield from iter_listings(active_only=True, path=path)


def save_parts(listing_id: str, payload: dict, path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO parts (listing_id, payload_json, extracted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                extracted_at = excluded.extracted_at
            """,
            (listing_id, json.dumps(payload, ensure_ascii=False), utcnow()),
        )
        sync_fts(conn, listing_id)


def save_results_batch(
    rows: list[tuple[str, dict, dict, bool, bool]],
    path: Path | None = None,
) -> None:
    now = utcnow()
    parts_rows = []
    analysis_rows = []
    kind_rows = []
    ids = []
    for listing_id, parts, analysis, is_desktop, is_laptop in rows:
        ids.append(listing_id)
        parts_rows.append((listing_id, json.dumps(parts, ensure_ascii=False), now))
        cost, resale, profit = _plan_money(analysis)
        analysis_rows.append(
            (
                listing_id,
                analysis["score"],
                analysis.get("verdict"),
                analysis.get("platform_score"),
                analysis.get("headroom_score"),
                analysis.get("expandability_score"),
                analysis.get("value_score"),
                1 if analysis.get("has_potential") else 0,
                analysis.get("socket"),
                json.dumps(analysis, ensure_ascii=False),
                now,
                cost,
                resale,
                profit,
            )
        )
        kind_rows.append(
            (1 if is_desktop and not is_laptop else 0, 1 if is_laptop else 0, listing_id)
        )
    with connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO parts (listing_id, payload_json, extracted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                extracted_at = excluded.extracted_at
            """,
            parts_rows,
        )
        conn.executemany(
            """
            INSERT INTO analyses (
                listing_id, score, verdict, platform_score, headroom_score,
                expandability_score, value_score, has_potential, socket,
                payload_json, analyzed_at, upgrade_cost_eur, resale_eur, profit_eur
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                score = excluded.score,
                verdict = excluded.verdict,
                platform_score = excluded.platform_score,
                headroom_score = excluded.headroom_score,
                expandability_score = excluded.expandability_score,
                value_score = excluded.value_score,
                has_potential = excluded.has_potential,
                socket = excluded.socket,
                payload_json = excluded.payload_json,
                analyzed_at = excluded.analyzed_at,
                upgrade_cost_eur = excluded.upgrade_cost_eur,
                resale_eur = excluded.resale_eur,
                profit_eur = excluded.profit_eur
            """,
            analysis_rows,
        )
        conn.executemany(
            """
            UPDATE listings
            SET is_desktop = ?,
                is_active = CASE WHEN ? THEN 0 ELSE is_active END
            WHERE id = ?
            """,
            kind_rows,
        )
        for listing_id in ids:
            sync_fts(conn, listing_id)


def save_analysis(listing_id: str, analysis: dict, path: Path | None = None) -> None:
    cost, resale, profit = _plan_money(analysis)
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO analyses (
                listing_id, score, verdict, platform_score, headroom_score,
                expandability_score, value_score, has_potential, socket,
                payload_json, analyzed_at, upgrade_cost_eur, resale_eur, profit_eur
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                score = excluded.score,
                verdict = excluded.verdict,
                platform_score = excluded.platform_score,
                headroom_score = excluded.headroom_score,
                expandability_score = excluded.expandability_score,
                value_score = excluded.value_score,
                has_potential = excluded.has_potential,
                socket = excluded.socket,
                payload_json = excluded.payload_json,
                analyzed_at = excluded.analyzed_at,
                upgrade_cost_eur = excluded.upgrade_cost_eur,
                resale_eur = excluded.resale_eur,
                profit_eur = excluded.profit_eur
            """,
            (
                listing_id,
                analysis["score"],
                analysis.get("verdict"),
                analysis.get("platform_score"),
                analysis.get("headroom_score"),
                analysis.get("expandability_score"),
                analysis.get("value_score"),
                1 if analysis.get("has_potential") else 0,
                analysis.get("socket"),
                json.dumps(analysis, ensure_ascii=False),
                utcnow(),
                cost,
                resale,
                profit,
            ),
        )


def top_upgrades(min_score: float, limit: int = 40, path: Path | None = None) -> list[dict]:
    from skelbiu_pc.db.search import price_series

    with connect(path) as conn:
        rows = conn.execute(
            f"""
            SELECT l.id, l.url, l.title, l.price_cents, l.city, l.condition,
                   a.score, a.verdict, a.socket, a.has_potential, a.payload_json,
                   p.payload_json AS parts_json
            FROM analyses a
            JOIN listings l ON l.id = a.listing_id
            LEFT JOIN parts p ON p.listing_id = l.id
            WHERE l.is_active = 1 AND a.score >= ?
              AND {NOT_LAPTOP_SQL}
            ORDER BY a.score DESC
            LIMIT ?
            """,
            (min_score, limit),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["analysis"] = json.loads(item.pop("payload_json"))
            parts_json = item.pop("parts_json")
            item["parts"] = json.loads(parts_json) if parts_json else {}
            item["price_points"] = price_series(item["id"], path)
            out.append(item)
        return out


def save_advice(listing_id: str, advice: dict, path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO advice (
                listing_id, action, interest, summary, flags_json,
                payload_json, model, advised_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                action = excluded.action,
                interest = excluded.interest,
                summary = excluded.summary,
                flags_json = excluded.flags_json,
                payload_json = excluded.payload_json,
                model = excluded.model,
                advised_at = excluded.advised_at
            """,
            (
                listing_id,
                advice["action"],
                advice["interest"],
                advice.get("summary"),
                json.dumps(advice.get("flags") or [], ensure_ascii=False),
                json.dumps(advice, ensure_ascii=False),
                advice.get("model"),
                utcnow(),
            ),
        )


def listings_for_advice(
    *,
    min_score: float = 40.0,
    limit: int = 80,
    only_missing: bool = True,
    listing_id: str | None = None,
    path: Path | None = None,
) -> list[dict]:
    sql = f"""
        SELECT l.id, l.title, l.price_cents, l.city, l.description,
               a.score, a.verdict, a.socket, a.payload_json,
               p.payload_json AS parts_json
        FROM listings l
        JOIN analyses a ON a.listing_id = l.id
        LEFT JOIN parts p ON p.listing_id = l.id
        LEFT JOIN advice v ON v.listing_id = l.id
        WHERE l.is_active = 1
          AND {NOT_LAPTOP_SQL}
    """
    params: list = []
    if listing_id:
        sql += " AND l.id = ?"
        params.append(listing_id)
    else:
        sql += " AND a.score >= ?"
        params.append(min_score)
        if only_missing:
            sql += " AND v.listing_id IS NULL"
        sql += """
            ORDER BY (l.description IS NULL OR l.description = ''),
                     a.has_potential DESC, a.score DESC
        """
        sql += " LIMIT ?"
        params.append(limit)
    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        parts_json = item.pop("parts_json")
        analysis = json.loads(item.pop("payload_json") or "{}")
        item["parts"] = json.loads(parts_json) if parts_json else {}
        item["analysis"] = analysis
        item["plan"] = analysis.get("plan") or {}
        item["price_eur"] = (item["price_cents"] / 100) if item.get("price_cents") is not None else None
        out.append(item)
    return out
