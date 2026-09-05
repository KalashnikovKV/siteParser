"""Локальная SQLite: снимок объявлений, история цен, разбор частей, оценки."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from skelbiu_pc.config import DB_PATH


_LAPTOP_TITLE_BITS = (
    "nesiojam",
    "nešiojam",
    "ноутбук",
    "laptop",
    "notebook",
    "macbook",
    "thinkpad",
    "latitude",
    "elitebook",
    "ideapad",
    "zenbook",
    "vivobook",
)

_NOT_LAPTOP_SQL = """
    ifnull(l.is_desktop, 1) = 1
    AND ifnull(json_extract(p.payload_json, '$.is_laptop'), 0) != 1
"""


def _looks_like_laptop(title: str | None) -> bool:
    low = (title or "").lower()
    return any(bit in low for bit in _LAPTOP_TITLE_BITS)


def _guess_desktop(title: str | None) -> int | None:
    if _looks_like_laptop(title):
        return 0
    low = (title or "").lower()
    if any(x in low for x in ("stacionar", "стационар", "desktop", "tower")):
        return 1
    return None


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect(path: Path | None = None):
    db_path = path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                price_cents INTEGER,
                card_price_cents INTEGER,
                currency TEXT DEFAULT 'EUR',
                city TEXT,
                condition TEXT,
                description TEXT,
                attributes_json TEXT,
                is_desktop INTEGER,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_detail_at TEXT,
                is_active INTEGER DEFAULT 1,
                source TEXT DEFAULT 'skelbiu'
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                price_cents INTEGER,
                seen_at TEXT NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            );

            CREATE TABLE IF NOT EXISTS parts (
                listing_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                extracted_at TEXT NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            );

            CREATE TABLE IF NOT EXISTS analyses (
                listing_id TEXT PRIMARY KEY,
                score REAL NOT NULL,
                verdict TEXT,
                platform_score REAL,
                headroom_score REAL,
                expandability_score REAL,
                value_score REAL,
                has_potential INTEGER,
                socket TEXT,
                payload_json TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                upgrade_cost_eur REAL,
                resale_eur REAL,
                profit_eur REAL,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            );

            CREATE TABLE IF NOT EXISTS advice (
                listing_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                interest REAL NOT NULL,
                summary TEXT,
                flags_json TEXT,
                payload_json TEXT NOT NULL,
                model TEXT,
                advised_at TEXT NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            );

            CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                list_url TEXT,
                pages INTEGER DEFAULT 0,
                listings_seen INTEGER DEFAULT 0,
                new_listings INTEGER DEFAULT 0,
                price_changes INTEGER DEFAULT 0,
                details_fetched INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_listing
                ON price_history(listing_id, seen_at);
            CREATE INDEX IF NOT EXISTS idx_analyses_score
                ON analyses(score DESC);
            CREATE INDEX IF NOT EXISTS idx_listings_active_seen
                ON listings(is_active, last_seen_at);
            CREATE INDEX IF NOT EXISTS idx_listings_city
                ON listings(city);
            CREATE INDEX IF NOT EXISTS idx_listings_price
                ON listings(price_cents);
            """
        )
        _migrate_analysis_columns(conn)
        _migrate_listing_columns(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_profit ON analyses(profit_eur DESC)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_advice_interest ON advice(interest DESC)")
        _deactivate_laptops(conn)


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
    """Пишем страницу индекса одной транзакцией."""
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
    """Пишем карточку с индекса. Если цена сменилась — добавляем точку графика."""
    from skelbiu_pc.prices import resolve_listing_price

    now = utcnow()
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (card["id"],)).fetchone()
    title = card.get("title") or (row["title"] if row else None)
    description = row["description"] if row else None
    card_price = card.get("price_cents")
    price, _note = resolve_listing_price(card_price, title, description)
    result = {"new": False, "price_changed": False}

    laptop = _looks_like_laptop(card.get("title"))
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
                0 if laptop else _guess_desktop(card.get("title")),
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


def _migrate_listing_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN source TEXT DEFAULT 'skelbiu'")
        conn.execute("UPDATE listings SET source = 'skelbiu' WHERE source IS NULL")
    if "card_price_cents" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN card_price_cents INTEGER")
        conn.execute("UPDATE listings SET card_price_cents = price_cents")


def _deactivate_laptops(conn: sqlite3.Connection) -> None:
    likes = " OR ".join("lower(ifnull(l.title, '')) LIKE ?" for _ in _LAPTOP_TITLE_BITS)
    conn.execute(
        f"""
        UPDATE listings
        SET is_active = 0, is_desktop = 0
        WHERE id IN (
            SELECT l.id FROM listings l
            LEFT JOIN parts p ON p.listing_id = l.id
            WHERE l.is_active = 1 AND (
                l.is_desktop = 0
                OR ifnull(json_extract(p.payload_json, '$.is_laptop'), 0) = 1
                OR {likes}
            )
        )
        """,
        [f"%{bit}%" for bit in _LAPTOP_TITLE_BITS],
    )


def _migrate_analysis_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
    for name, decl in (
        ("upgrade_cost_eur", "REAL"),
        ("resale_eur", "REAL"),
        ("profit_eur", "REAL"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {name} {decl}")


def _plan_money(analysis: dict) -> tuple[float | None, float | None, float | None]:
    plan = analysis.get("plan") or {}
    return plan.get("upgrade_cost_eur"), plan.get("resale_eur"), plan.get("profit_eur")


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
            sql += " AND l.last_detail_at IS NULL"
        else:
            sql += """
              AND (
                    l.last_detail_at IS NULL
                 OR l.description IS NULL
                 OR l.description = ''
                 OR l.last_detail_at < datetime('now', ?)
              )
            """
            params.append(f"-{ttl_days} days")
        sql += f" AND {_NOT_LAPTOP_SQL}"
        if candidates_only:
            sql += """
              AND (
                    ifnull(a.score, 0) >= ?
                 OR a.listing_id IS NULL
              )
            """
            params.append(score_floor)
        sql += """
            ORDER BY l.last_detail_at IS NOT NULL,
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


def save_results_batch(
    rows: list[tuple[str, dict, dict, bool, bool]],
    path: Path | None = None,
) -> None:
    """Один транзакционный проход: части, оценка, desktop/laptop."""
    now = utcnow()
    parts_rows = []
    analysis_rows = []
    kind_rows = []
    for listing_id, parts, analysis, is_desktop, is_laptop in rows:
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
              AND {_NOT_LAPTOP_SQL}
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


def search_listings(
    *,
    q: str | None = None,
    min_price_eur: float | None = None,
    max_price_eur: float | None = None,
    city: str | None = None,
    socket: str | None = None,
    source: str | None = None,
    potential: bool | None = None,
    kind: str = "all",
    sort: str = "score",
    page: int = 1,
    limit: int = 30,
    active_only: bool = True,
    path: Path | None = None,
) -> dict:
    where = ["1=1"]
    params: list = []
    if active_only:
        where.append("l.is_active = 1")
    if q:
        like = f"%{q.strip()}%"
        where.append(
            """(
                l.title LIKE ? OR ifnull(l.description, '') LIKE ?
                OR ifnull(p.payload_json, '') LIKE ?
            )"""
        )
        params.extend([like, like, like])
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
    if kind == "laptop":
        where.append("1 = 0")
    else:
        where.append(_NOT_LAPTOP_SQL)

    order = {
        "score": "a.score IS NULL, a.score DESC, l.last_seen_at DESC",
        "price_asc": "l.price_cents IS NULL, l.price_cents ASC",
        "price_desc": "l.price_cents IS NULL, l.price_cents DESC",
        "seen": "l.last_seen_at DESC",
        "title": "l.title COLLATE NOCASE",
        "profit": "a.profit_eur IS NULL, a.profit_eur DESC",
        "resale": "a.resale_eur IS NULL, a.resale_eur DESC",
        "cost": "a.upgrade_cost_eur IS NULL, a.upgrade_cost_eur ASC",
        "ai": "v.interest IS NULL, v.interest DESC, a.score DESC",
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
          AND {_NOT_LAPTOP_SQL}
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


def stats(path: Path | None = None) -> dict:
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
    return {"cities": cities, "sockets": sockets, "sources": sources}


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
