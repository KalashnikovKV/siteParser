"""Статус фоновых задач в SQLite — переживает restart контейнера."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skelbiu_pc.db.connection import connect, utcnow

KINDS = ("analyze", "details", "advise")


def empty_job(kind: str | None = None) -> dict[str, Any]:
    return {
        "running": False,
        "kind": kind,
        "done": 0,
        "total": 0,
        "analyzed": 0,
        "error": None,
        "stats": None,
    }


def job_status(kind: str, path: Path | None = None) -> dict[str, Any]:
    with connect(path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE kind = ?", (kind,)).fetchone()
    if row is None:
        return empty_job(None)
    stats = json.loads(row["stats_json"]) if row["stats_json"] else None
    running = bool(row["running"])
    return {
        "running": running,
        "kind": kind if running else None,
        "done": row["done"] or 0,
        "total": row["total"] or 0,
        "analyzed": row["analyzed"] or 0,
        "error": row["error"],
        "stats": stats,
    }


def try_begin_job(kind: str, path: Path | None = None) -> dict[str, Any] | None:
    now = utcnow()
    with connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE jobs
            SET running = 1, done = 0, total = 0, analyzed = 0,
                error = NULL, stats_json = NULL, updated_at = ?
            WHERE kind = ? AND running = 0
            """,
            (now, kind),
        )
        if cur.rowcount != 1:
            return None
    return job_status(kind, path)


def update_job(kind: str, path: Path | None = None, **kwargs: Any) -> None:
    allowed = {"running", "done", "total", "analyzed", "error", "stats"}
    fields = []
    values: list[Any] = []
    for key, value in kwargs.items():
        if key not in allowed:
            continue
        column = "stats_json" if key == "stats" else key
        fields.append(f"{column} = ?")
        if key == "running":
            values.append(1 if value else 0)
        elif key == "stats":
            values.append(json.dumps(value, ensure_ascii=False) if value is not None else None)
        else:
            values.append(value)
    if not fields:
        return
    fields.append("updated_at = ?")
    values.append(utcnow())
    values.append(kind)
    with connect(path) as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE kind = ?", values)


def finish_job(
    kind: str,
    path: Path | None = None,
    *,
    error: str | None = None,
    **kwargs: Any,
) -> None:
    payload = dict(kwargs)
    payload["running"] = False
    payload["error"] = error
    update_job(kind, path, **payload)
