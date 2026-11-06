"""Фоновые задачи: пересчёт, описания и модель могут идти параллельно.

Статус лежит в SQLite, чтобы переживать restart контейнера.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from skelbiu_pc import db
from skelbiu_pc.db.jobs_store import KINDS
from skelbiu_pc.pipeline import advise_candidates, analyze_all, fetch_missing_details

_lock = threading.Lock()
_local_running: set[str] = set()


def status(kind: str | None = None, path: Path | None = None) -> dict[str, Any]:
    if kind:
        return db.job_status(kind, path)
    for name in KINDS:
        slot = db.job_status(name, path)
        if slot["running"]:
            return slot
    return db.empty_job()


def _begin(kind: str, path: Path | None) -> dict[str, Any] | None:
    with _lock:
        if kind in _local_running:
            return None
        started = db.try_begin_job(kind, path)
        if started is None:
            return None
        _local_running.add(kind)
        return started


def _done(kind: str) -> None:
    with _lock:
        _local_running.discard(kind)


def start(path=None, only_missing: bool = True) -> dict[str, Any]:
    if _begin("analyze", path) is None:
        return status("analyze", path)

    def worker() -> None:
        try:
            count = analyze_all(path, only_missing=only_missing)
            stats = db.stats(path)
            db.finish_job("analyze", path, analyzed=count, done=count, stats=stats)
        except Exception as exc:
            db.finish_job("analyze", path, error=str(exc))
        finally:
            _done("analyze")

    threading.Thread(target=worker, daemon=True).start()
    return status("analyze", path)


def start_details(
    path=None,
    limit: int | None = None,
    headed: bool = False,
    *,
    refresh: bool = True,
) -> dict[str, Any]:
    from skelbiu_pc.config import DETAIL_BATCH_LIMIT, DETAIL_TTL_DAYS

    if _begin("details", path) is None:
        return status("details", path)
    batch = DETAIL_BATCH_LIMIT if limit is None else limit
    pending = db.listings_needing_details(
        DETAIL_TTL_DAYS,
        limit=batch,
        path=path,
        missing_only=not refresh,
        candidates_only=False,
    )
    db.update_job("details", path, total=len(pending), done=0, analyzed=0)
    if not pending:
        db.finish_job("details", path, stats=db.stats(path))
        _done("details")
        return status("details", path)

    def on_progress(done: int, total: int) -> None:
        payload: dict[str, Any] = {"done": done, "total": total, "analyzed": done}
        if done % 15 == 0:
            payload["stats"] = db.stats(path)
        db.update_job("details", path, **payload)

    def worker() -> None:
        try:
            result = fetch_missing_details(
                path=path,
                limit=batch,
                headed=headed,
                missing_only=not refresh,
                candidates_only=False,
                progress=on_progress,
            )
            db.finish_job(
                "details",
                path,
                done=result["fetched"],
                total=result["total"],
                analyzed=result["fetched"],
                stats=db.stats(path),
                error=result.get("error"),
            )
        except Exception as exc:
            db.finish_job("details", path, error=str(exc))
        finally:
            _done("details")

    threading.Thread(target=worker, daemon=True).start()
    return status("details", path)


def start_advise(
    path=None,
    limit: int = 80,
    min_score: float = 40.0,
    only_missing: bool = True,
    listing_id: str | None = None,
) -> dict[str, Any]:
    if _begin("advise", path) is None:
        return status("advise", path)

    def on_progress(done: int, total: int) -> None:
        db.update_job("advise", path, done=done, total=total, analyzed=done)

    def worker() -> None:
        try:
            result = advise_candidates(
                path=path,
                min_score=min_score,
                limit=limit,
                only_missing=only_missing,
                listing_id=listing_id,
                progress=on_progress,
            )
            db.finish_job(
                "advise",
                path,
                done=result["advised"],
                total=result["total"],
                analyzed=result["advised"],
                stats=db.stats(path),
                error=result.get("error"),
            )
        except Exception as exc:
            db.finish_job("advise", path, error=str(exc))
        finally:
            _done("advise")

    threading.Thread(target=worker, daemon=True).start()
    return status("advise", path)
