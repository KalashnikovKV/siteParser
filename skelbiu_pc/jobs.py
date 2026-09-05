"""Фоновые задачи: пересчёт, описания и модель могут идти параллельно."""

from __future__ import annotations

import threading
from typing import Any

from skelbiu_pc import db
from skelbiu_pc.pipeline import advise_candidates, analyze_all, fetch_missing_details

KINDS = ("analyze", "details", "advise")


def _empty() -> dict[str, Any]:
    return {
        "running": False,
        "kind": None,
        "done": 0,
        "total": 0,
        "analyzed": 0,
        "error": None,
        "stats": None,
    }


_lock = threading.Lock()
_slots: dict[str, dict[str, Any]] = {kind: _empty() for kind in KINDS}


def status(kind: str | None = None) -> dict[str, Any]:
    with _lock:
        if kind:
            return dict(_slots[kind])
        running = next((slot for slot in _slots.values() if slot["running"]), None)
        return dict(running) if running else _empty()


def _set(slot: str, **kwargs) -> None:
    with _lock:
        _slots[slot].update(kwargs)


def _begin(kind: str) -> dict[str, Any] | None:
    with _lock:
        if _slots[kind]["running"]:
            return None
        _slots[kind].update(
            {
                "running": True,
                "kind": kind,
                "done": 0,
                "total": 0,
                "analyzed": 0,
                "error": None,
            }
        )
        return dict(_slots[kind])


def start(path=None, only_missing: bool = True) -> dict[str, Any]:
    if _begin("analyze") is None:
        return status("analyze")

    def worker() -> None:
        try:
            count = analyze_all(path, only_missing=only_missing)
            stats = db.stats(path)
            _set(
                "analyze",
                analyzed=count,
                done=count,
                stats=stats,
                error=None,
                running=False,
                kind=None,
            )
        except Exception as exc:
            _set("analyze", error=str(exc), running=False, kind=None)

    threading.Thread(target=worker, daemon=True).start()
    return status("analyze")


def start_details(path=None, limit: int | None = None, headed: bool = False) -> dict[str, Any]:
    from skelbiu_pc.config import DETAIL_TTL_DAYS

    if _begin("details") is None:
        return status("details")
    pending = db.listings_needing_details(
        DETAIL_TTL_DAYS,
        limit=limit,
        path=path,
        missing_only=True,
        candidates_only=False,
    )
    _set("details", total=len(pending), done=0, analyzed=0)
    if not pending:
        _set("details", running=False, kind=None, stats=db.stats(path), error=None)
        return status("details")

    def on_progress(done: int, total: int) -> None:
        stats = db.stats(path) if done % 15 == 0 else None
        payload: dict[str, Any] = {"done": done, "total": total, "analyzed": done}
        if stats:
            payload["stats"] = stats
        _set("details", **payload)

    def worker() -> None:
        try:
            result = fetch_missing_details(
                path=path,
                limit=limit,
                headed=headed,
                missing_only=True,
                candidates_only=False,
                progress=on_progress,
            )
            stats = db.stats(path)
            _set(
                "details",
                done=result["fetched"],
                total=result["total"],
                analyzed=result["fetched"],
                stats=stats,
                error=result.get("error"),
                running=False,
                kind=None,
            )
        except Exception as exc:
            _set("details", error=str(exc), running=False, kind=None)

    threading.Thread(target=worker, daemon=True).start()
    return status("details")


def start_advise(
    path=None,
    limit: int = 80,
    min_score: float = 40.0,
    only_missing: bool = True,
    listing_id: str | None = None,
) -> dict[str, Any]:
    if _begin("advise") is None:
        return status("advise")

    def on_progress(done: int, total: int) -> None:
        _set("advise", done=done, total=total, analyzed=done)

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
            stats = db.stats(path)
            _set(
                "advise",
                done=result["advised"],
                total=result["total"],
                analyzed=result["advised"],
                stats=stats,
                error=result.get("error"),
                running=False,
                kind=None,
            )
        except Exception as exc:
            _set("advise", error=str(exc), running=False, kind=None)

    threading.Thread(target=worker, daemon=True).start()
    return status("advise")
