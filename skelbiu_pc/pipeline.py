"""Загрузка через порт источника, разбор и апгрейд — только по локальной БД."""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from skelbiu_pc import db
from skelbiu_pc.config import DEFAULT_SOURCE, DETAIL_TTL_DAYS
from skelbiu_pc.parts import extract_parts
from skelbiu_pc.prices import resolve_listing_price
from skelbiu_pc.sources import SourceError, get_source
from skelbiu_pc.upgrade import analyze_upgrade

ProgressCb = Callable[[int, int], None]


def fetch_category(
    url: str | None = None,
    max_pages: int | None = None,
    limit_details: int | None = None,
    headed: bool = False,
    skip_details: bool = False,
    mark_inactive: bool = True,
    path: Path | None = None,
    source_name: str | None = None,
) -> dict:
    source = get_source(source_name or DEFAULT_SOURCE)
    list_url = url or source.info.homepage
    run_id = db.start_run(list_url, path)
    stats = {
        "pages": 0,
        "listings_seen": 0,
        "new_listings": 0,
        "price_changes": 0,
        "details_fetched": 0,
        "ok": True,
        "error": None,
        "source": source.info.name,
    }
    seen: set[str] = set()

    try:
        for page_num, cards in source.iter_index(list_url, max_pages=max_pages, headed=headed):
            stats["pages"] = page_num
            print(f"  страница {page_num}: {len(cards)} объявлений")
            stamped = []
            for card in cards:
                item = dict(card)
                item["id"] = source.qualify_id(str(item["id"]))
                item["source"] = source.info.name
                seen.add(item["id"])
                stamped.append(item)
            page_stats = db.upsert_cards(stamped, path)
            stats["listings_seen"] += page_stats["seen"]
            stats["new_listings"] += page_stats["new"]
            stats["price_changes"] += page_stats["price_changed"]
    except SourceError as exc:
        stats["ok"] = False
        stats["error"] = str(exc)
        print(f"Ошибка загрузки: {exc}", file=sys.stderr)
        db.finish_run(run_id, stats, path)
        return stats

    if seen and mark_inactive:
        inactive = db.mark_missing_inactive(seen, path)
        if inactive:
            print(f"  снято с публикации: {inactive}")

    if not skip_details:
        extra = fetch_missing_details(
            path=path,
            limit=limit_details,
            headed=headed,
            missing_only=False,
        )
        stats["details_fetched"] = extra["fetched"]
        if extra.get("error"):
            stats["ok"] = False
            stats["error"] = extra["error"]

    db.finish_run(run_id, stats, path)
    return stats


def _score_listing(listing: dict, path: Path | None = None) -> tuple[str, dict, dict, bool, bool]:
    resolved, note = resolve_listing_price(
        listing.get("card_price_cents")
        if listing.get("card_price_cents") is not None
        else listing.get("price_cents"),
        listing.get("title"),
        listing.get("description"),
    )
    if resolved is not None and resolved != listing.get("price_cents"):
        db.apply_price(listing["id"], resolved, path)
        listing["price_cents"] = resolved
    parts = extract_parts(
        listing.get("title") or "",
        listing.get("description") or "",
        listing.get("attributes") or {},
    )
    price_eur = (resolved / 100) if resolved is not None else None
    has_description = bool((listing.get("description") or "").strip())
    analysis = analyze_upgrade(parts, price_eur, has_description=has_description)
    analysis.price_note = note
    if note:
        analysis.reasons.insert(0, note)
    return listing["id"], parts.to_dict(), analysis.to_dict(), parts.is_desktop, parts.is_laptop


def analyze_one(listing: dict, path: Path | None = None) -> None:
    db.save_results_batch([_score_listing(listing, path)], path)


def analyze_all(path: Path | None = None, only_missing: bool = False) -> int:
    skip = db.analyzed_ids(path) if only_missing else set()
    batch: list[tuple[str, dict, dict, bool, bool]] = []
    for listing in db.iter_listings(active_only=False, path=path):
        if listing["id"] in skip:
            continue
        batch.append(_score_listing(listing, path))
    if batch:
        db.save_results_batch(batch, path)
    return len(batch)


def fetch_missing_details(
    path: Path | None = None,
    limit: int | None = None,
    headed: bool = False,
    missing_only: bool = True,
    candidates_only: bool = False,
    progress: ProgressCb | None = None,
) -> dict:
    """Карточки разных источников разбирает каждый адаптер сам."""
    todo = db.listings_needing_details(
        DETAIL_TTL_DAYS,
        limit=limit,
        path=path,
        missing_only=missing_only,
        candidates_only=candidates_only,
    )
    result = {"fetched": 0, "total": len(todo), "error": None}
    if progress:
        progress(0, len(todo))
    if not todo:
        return result
    scope = "кандидаты" if candidates_only else "стационарные без текста"
    print(f"  к открытию описаний: {len(todo)} ({scope})")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in todo:
        grouped[row.get("source") or DEFAULT_SOURCE].append(row)
    try:
        for source_name, rows in grouped.items():
            source = get_source(source_name)
            for detail in source.iter_details([x["url"] for x in rows], headed=headed):
                if detail.get("id"):
                    detail["id"] = source.qualify_id(str(detail["id"]))
                    detail["source"] = source.info.name
                db.update_detail(detail, path)
                full = db.listing_for_analyze(detail["id"], path)
                if full:
                    analyze_one(full, path)
                result["fetched"] += 1
                if progress:
                    progress(result["fetched"], result["total"])
                if result["fetched"] % 10 == 0:
                    print(f"  открыто {result['fetched']}/{result['total']}")
    except (SourceError, KeyError) as exc:
        result["error"] = str(exc)
        print(f"Ошибка детализации: {exc}", file=sys.stderr)
    return result


def advise_candidates(
    path: Path | None = None,
    min_score: float = 40.0,
    limit: int = 80,
    only_missing: bool = True,
    listing_id: str | None = None,
    progress: ProgressCb | None = None,
) -> dict:
    from skelbiu_pc.advisors import get_advisor
    from skelbiu_pc.advisors.guard import harden_advice

    try:
        advisor = get_advisor()
    except RuntimeError as exc:
        return {"advised": 0, "total": 0, "error": str(exc)}
    ok, error = advisor.available()
    if not ok:
        return {"advised": 0, "total": 0, "error": error}
    todo = db.listings_for_advice(
        min_score=min_score,
        limit=limit,
        only_missing=only_missing,
        listing_id=listing_id,
        path=path,
    )
    if listing_id and not todo:
        return {
            "advised": 0,
            "total": 0,
            "error": "нет разбора правилами — сначала пересчитайте",
        }
    result = {"advised": 0, "total": len(todo), "error": None}
    print(f"  к разбору моделью: {len(todo)}")
    for row in todo:
        try:
            advice = advisor.review(
                {
                    "title": row.get("title"),
                    "price_eur": row.get("price_eur"),
                    "city": row.get("city"),
                    "description": row.get("description"),
                    "parts": row.get("parts") or {},
                    "analysis": row.get("analysis") or {},
                    "plan": row.get("plan") or {},
                }
            )
        except Exception as exc:
            print(f"  лот {row['id']}: {exc}", file=sys.stderr)
            if "не ответила" in str(exc) or "недоступн" in str(exc):
                result["error"] = str(exc)
                break
            from skelbiu_pc.advisors.port import Advice

            advice = Advice(
                action="inspect",
                interest=40,
                summary="Модель споткнулась на этом лоте, разбор пропущен.",
                flags=["parse_error"],
                model=getattr(advisor, "model", ""),
            )
        seller_text = f"{row.get('title') or ''}\n{row.get('description') or ''}"
        advice = harden_advice(advice, seller_text)
        db.save_advice(row["id"], advice.to_dict(), path)
        result["advised"] += 1
        if progress:
            progress(result["advised"], result["total"])
        if result["advised"] % 5 == 0:
            print(f"  модель {result['advised']}/{result['total']}")
    return result
