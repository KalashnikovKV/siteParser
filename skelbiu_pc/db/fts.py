"""FTS5 по title, description и комплектующим — без LIKE по JSON."""

from __future__ import annotations

import json
import re
import sqlite3

_TOKEN_RE = re.compile(r"[\w./+-]+", re.UNICODE)


def fts_match_query(raw: str) -> str | None:
    tokens = [tok.replace('"', "") for tok in _TOKEN_RE.findall(raw.strip())]
    tokens = [tok for tok in tokens if tok]
    if not tokens:
        return None
    return " AND ".join(f'"{tok}"' for tok in tokens)


def _parts_text(payload_json: str | None) -> str:
    if not payload_json:
        return ""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return payload_json
    bits = []
    for key in ("cpu", "gpu", "ram", "motherboard", "chipset", "socket", "psu", "storage"):
        value = payload.get(key)
        if value:
            bits.append(str(value))
    return " ".join(bits)


def sync_fts(conn: sqlite3.Connection, listing_id: str) -> None:
    row = conn.execute(
        """
        SELECT l.title, l.description, p.payload_json
        FROM listings l
        LEFT JOIN parts p ON p.listing_id = l.id
        WHERE l.id = ?
        """,
        (listing_id,),
    ).fetchone()
    if row is None:
        conn.execute("DELETE FROM listings_fts WHERE listing_id = ?", (listing_id,))
        return
    conn.execute("DELETE FROM listings_fts WHERE listing_id = ?", (listing_id,))
    conn.execute(
        """
        INSERT INTO listings_fts (listing_id, title, description, parts)
        VALUES (?, ?, ?, ?)
        """,
        (
            listing_id,
            row["title"] or "",
            row["description"] or "",
            _parts_text(row["payload_json"]),
        ),
    )


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM listings_fts")
    rows = conn.execute(
        """
        SELECT l.id, l.title, l.description, p.payload_json
        FROM listings l
        LEFT JOIN parts p ON p.listing_id = l.id
        """
    ).fetchall()
    conn.executemany(
        """
        INSERT INTO listings_fts (listing_id, title, description, parts)
        VALUES (?, ?, ?, ?)
        """,
        [
            (row["id"], row["title"] or "", row["description"] or "", _parts_text(row["payload_json"]))
            for row in rows
        ],
    )
