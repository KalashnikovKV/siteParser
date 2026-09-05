"""Схема и миграции. Поиск ноутбуков — те же корни, что в parts.py."""

from __future__ import annotations

import sqlite3

from skelbiu_pc.db.connection import connect
from skelbiu_pc.db.fts import rebuild_fts
from skelbiu_pc.parts import LAPTOP_TITLE_BITS

NOT_LAPTOP_SQL = """
    ifnull(l.is_desktop, 1) = 1
    AND ifnull(json_extract(p.payload_json, '$.is_laptop'), 0) != 1
"""

_SCHEMA = """
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

            CREATE TABLE IF NOT EXISTS jobs (
                kind TEXT PRIMARY KEY,
                running INTEGER DEFAULT 0,
                done INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                analyzed INTEGER DEFAULT 0,
                error TEXT,
                stats_json TEXT,
                updated_at TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS listings_fts USING fts5(
                listing_id UNINDEXED,
                title,
                description,
                parts
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

_JOB_KINDS = ("analyze", "details", "advise")


def init_db(path=None) -> None:
    with connect(path) as conn:
        conn.executescript(_SCHEMA)
        _migrate_analysis_columns(conn)
        _migrate_listing_columns(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_profit ON analyses(profit_eur DESC)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_advice_interest ON advice(interest DESC)")
        _ensure_job_rows(conn)
        conn.execute("UPDATE jobs SET running = 0 WHERE running = 1")
        _deactivate_laptops(conn)
        fts_n = conn.execute("SELECT count(*) FROM listings_fts").fetchone()[0]
        listings_n = conn.execute("SELECT count(*) FROM listings").fetchone()[0]
        if fts_n != listings_n:
            rebuild_fts(conn)


def _ensure_job_rows(conn: sqlite3.Connection) -> None:
    for kind in _JOB_KINDS:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (kind, running, done, total, analyzed) VALUES (?, 0, 0, 0, 0)",
            (kind,),
        )


def _migrate_listing_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN source TEXT DEFAULT 'skelbiu'")
        conn.execute("UPDATE listings SET source = 'skelbiu' WHERE source IS NULL")
    if "card_price_cents" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN card_price_cents INTEGER")
        conn.execute("UPDATE listings SET card_price_cents = price_cents")


def _migrate_analysis_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
    for name, decl in (
        ("upgrade_cost_eur", "REAL"),
        ("resale_eur", "REAL"),
        ("profit_eur", "REAL"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {name} {decl}")


def _deactivate_laptops(conn: sqlite3.Connection) -> None:
    likes = " OR ".join("lower(ifnull(l.title, '')) LIKE ?" for _ in LAPTOP_TITLE_BITS)
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
        [f"%{bit}%" for bit in LAPTOP_TITLE_BITS],
    )
