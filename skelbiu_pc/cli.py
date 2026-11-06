"""CLI: fetch качает всю /kompiuteriai/, поиск и апгрейд идут уже по локальной БД."""

from __future__ import annotations

import argparse
import sys

from skelbiu_pc import db
from skelbiu_pc.config import (
    ADVISE_DEFAULT_LIMIT,
    API_HOST,
    API_PORT,
    DEFAULT_SOURCE,
    MIN_UPGRADE_SCORE,
)
from skelbiu_pc.pipeline import advise_candidates, analyze_all, fetch_category, fetch_missing_details
from skelbiu_pc.report import format_history, format_top, write_json
from skelbiu_pc.seed import seed, seed_if_empty


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Качает объявления через адаптер источника в локальную БД, "
            "а поиск и оценку апгрейда делает уже по ней."
        )
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch = sub.add_parser("fetch", help="Скачать категорию выбранного источника в SQLite")
    fetch.add_argument("--source", default=DEFAULT_SOURCE, help="Адаптер: skelbiu, позже другие")
    fetch.add_argument("--url", default=None, help="Переопределить URL индекса источника")
    fetch.add_argument("--max-pages", type=int, default=None)
    fetch.add_argument("--limit-details", type=int, default=None)
    fetch.add_argument("--headed", action="store_true")
    fetch.add_argument("--skip-details", action="store_true")
    fetch.add_argument(
        "--keep-existing",
        action="store_true",
        help="Не помечать отсутствующие в этом URL объявления неактивными",
    )

    details = sub.add_parser("details", help="Докачать полные описания объявлений")
    details.add_argument("--limit", type=int, default=None)
    details.add_argument("--headed", action="store_true")
    details.add_argument(
        "--refresh",
        action="store_true",
        help="Ещё раз открыть карточки с пустым/устаревшим описанием",
    )
    details.add_argument(
        "--candidates",
        action="store_true",
        help="Только стационарные с баллом ≥ 30",
    )

    analyze = sub.add_parser("analyze", help="Разбор и апгрейд только по локальной БД")
    analyze.add_argument("--min-score", type=float, default=MIN_UPGRADE_SCORE)
    analyze.add_argument("--top", type=int, default=25)

    advise = sub.add_parser("advise", help="Локальная модель смотрит кандидатов из БД")
    advise.add_argument("listing_id", nargs="?", help="Один лот; без него — топ по оценке")
    advise.add_argument("--limit", type=int, default=ADVISE_DEFAULT_LIMIT)
    advise.add_argument("--min-score", type=float, default=MIN_UPGRADE_SCORE)
    advise.add_argument("--force", action="store_true", help="Переспросить уже разобранные")

    report = sub.add_parser("report", help="Кандидаты из уже посчитанной БД")
    report.add_argument("--min-score", type=float, default=MIN_UPGRADE_SCORE)
    report.add_argument("--top", type=int, default=25)

    history = sub.add_parser("history", help="График цены одного объявления")
    history.add_argument("listing_id")

    serve = sub.add_parser("serve", help="API + фронтенд над локальной БД")
    serve.add_argument("--host", default=API_HOST)
    serve.add_argument("--port", type=int, default=API_PORT)
    serve.add_argument("--seed", action="store_true", help="Если БД пустая — залить демо")

    seed_cmd = sub.add_parser("seed", help="Залить демо-объявления в пустую БД")
    seed_cmd.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    db.init_db()

    if args.cmd == "fetch":
        print(f"Загрузка источника {args.source}: {args.url or 'URL по умолчанию'}")
        stats = fetch_category(
            url=args.url,
            source_name=args.source,
            max_pages=args.max_pages,
            limit_details=args.limit_details,
            headed=args.headed,
            skip_details=args.skip_details,
            mark_inactive=not args.keep_existing,
        )
        print(
            f"Готово: страниц {stats['pages']}, объявлений {stats['listings_seen']}, "
            f"новых {stats['new_listings']}, смен цены {stats['price_changes']}, "
            f"описаний {stats['details_fetched']}"
        )
        print("Дальше: python -m skelbiu_pc analyze   или   python -m skelbiu_pc serve")
        return 0 if stats["ok"] else 2

    if args.cmd == "details":
        result = fetch_missing_details(
            limit=args.limit,
            headed=args.headed,
            missing_only=not args.refresh,
            candidates_only=args.candidates,
        )
        print(f"Открыто описаний: {result['fetched']} из {result['total']}")
        if result.get("error"):
            print(result["error"], file=sys.stderr)
            return 2
        return 0

    if args.cmd == "analyze":
        count = analyze_all()
        print(f"Пересчитано по локальной БД: {count}")
        _print_report(args.min_score, args.top)
        return 0

    if args.cmd == "advise":
        result = advise_candidates(
            min_score=args.min_score,
            limit=args.limit,
            only_missing=not args.force,
            listing_id=args.listing_id,
        )
        print(f"Модель разобрала: {result['advised']} из {result['total']}")
        if result.get("error"):
            print(result["error"], file=sys.stderr)
            return 2
        return 0

    if args.cmd == "report":
        _print_report(args.min_score, args.top)
        return 0

    if args.cmd == "history":
        return cmd_history(args.listing_id)

    if args.cmd == "serve":
        if args.seed:
            n = seed_if_empty()
            if n:
                print(f"БД была пустая, залито демо: {n}")
        return cmd_serve(args.host, args.port)

    if args.cmd == "seed":
        n = seed() if args.force or db.stats()["total"] == 0 else 0
        print(f"Демо-записей обработано: {n}" if n else "БД уже не пустая. Нужен --force.")
        return 0
    return 1


def _print_report(min_score: float, top: int) -> None:
    rows = db.top_upgrades(min_score, limit=top)
    print()
    print(format_top(rows))
    if rows:
        path = write_json(rows)
        print(f"\nJSON: {path}")


def cmd_history(listing_id: str) -> int:
    item = db.get_listing(listing_id)
    points = db.price_series(listing_id)
    title = item.get("title") if item else None
    print(format_history(listing_id, title, points))
    return 0 if points else 1


def cmd_serve(host: str, port: int) -> int:
    import uvicorn

    from skelbiu_pc.api import create_app
    from skelbiu_pc.security import SecuritySettings, is_loopback_host, is_wildcard_host

    settings = SecuritySettings.from_env(host)
    if not is_loopback_host(host) and not settings.auth_enabled:
        print(
            f"Отказ: на {host} интерфейс виден из сети, а пароль не задан.\n"
            "Задайте SKELBIU_PASSWORD (логин — SKELBIU_USER, по умолчанию skelbiu)\n"
            "и SKELBIU_ALLOWED_HOSTS=<IP или имя, по которому открываете UI>.",
            file=sys.stderr,
        )
        return 2
    shown = "127.0.0.1" if is_wildcard_host(host) else host
    if ":" in shown:
        shown = f"[{shown}]"
    print(f"UI:  http://{shown}:{port}/  (после npm run build в web/)")
    print(f"API: http://{shown}:{port}/api/stats")
    print("Dev: npm run dev в web/  →  http://127.0.0.1:5173")
    if settings.auth_enabled:
        print(f"Вход по паролю, логин {settings.username}")
    if is_wildcard_host(host):
        extra = sorted(settings.allowed_hosts)
        print(f"Разрешённые Host: {', '.join(extra)} (ещё — через SKELBIU_ALLOWED_HOSTS)")
    uvicorn.run(
        create_app(security=settings),
        host=host,
        port=port,
        reload=False,
        server_header=False,
    )
    return 0
