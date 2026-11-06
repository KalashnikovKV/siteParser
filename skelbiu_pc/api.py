"""HTTP API над локальной БД. Поиск и апгрейд не ходят на skelbiu.lt."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from skelbiu_pc import __version__, db
from skelbiu_pc.advisors import advisor_status
from skelbiu_pc.config import ADVISE_DEFAULT_LIMIT, API_HOST, MIN_UPGRADE_SCORE, ROOT
from skelbiu_pc.db.jobs_store import KINDS
from skelbiu_pc.jobs import start as start_analyze
from skelbiu_pc.jobs import start_advise, start_details
from skelbiu_pc.jobs import status as job_status
from skelbiu_pc.pipeline import advise_candidates
from skelbiu_pc.security import SecurityMiddleware, SecuritySettings
from skelbiu_pc.sources import list_sources

WEB_DIST = ROOT / "web" / "dist"
MAX_EUR = 1_000_000
STREAM_POLL_SEC = 0.5
STREAM_MAX_SEC = 30 * 60
ADVICE_FILTER = r"^(any|(buy|inspect|skip)(,(buy|inspect|skip)){0,2})$"

ListingId = Annotated[
    str, PathParam(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
]


def create_app(
    db_path: Path | None = None,
    *,
    security: SecuritySettings | None = None,
    web_dist: Path | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_db(db_path)
        yield

    app = FastAPI(
        title="Skelbiu PC",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        SecurityMiddleware,
        settings=security or SecuritySettings.from_env(API_HOST),
    )

    @app.get("/api/health")
    def api_health():
        return {"ok": True}

    @app.get("/api/stats")
    def api_stats():
        return db.stats(db_path)

    @app.get("/api/filters")
    def api_filters():
        return db.filter_options(db_path)

    @app.get("/api/sources")
    def api_sources():
        return {
            "items": [
                {"name": item.name, "title": item.title, "homepage": item.homepage}
                for item in list_sources()
            ]
        }

    @app.get("/api/listings")
    def api_listings(
        q: str | None = Query(None, max_length=200),
        min_price: float | None = Query(None, ge=0, le=MAX_EUR),
        max_price: float | None = Query(None, ge=0, le=MAX_EUR),
        city: str | None = Query(None, max_length=100),
        socket: str | None = Query(None, max_length=40),
        source: str | None = Query(None, max_length=40),
        potential: bool | None = None,
        advice: str | None = Query(None, pattern=ADVICE_FILTER),
        min_score: float | None = Query(None, ge=0, le=100),
        min_profit: float | None = Query(None, ge=-MAX_EUR, le=MAX_EUR),
        has_description: bool | None = None,
        preset: str | None = Query(None, max_length=20),
        kind: str = Query("desktop", pattern="^(all|desktop|laptop)$"),
        sort: str = Query(
            "score",
            pattern="^(score|price_asc|price_desc|seen|title|profit|resale|cost|ai)$",
        ),
        page: int = Query(1, ge=1, le=10_000),
        limit: int = Query(30, ge=1, le=100),
    ):
        return db.search_listings(
            q=q,
            min_price_eur=min_price,
            max_price_eur=max_price,
            city=city,
            socket=socket,
            source=source,
            potential=potential,
            advice=advice,
            min_score=min_score,
            min_profit_eur=min_profit,
            has_description=has_description,
            preset=preset,
            kind=kind,
            sort=sort,
            page=page,
            limit=limit,
            path=db_path,
        )

    @app.get("/api/picks")
    def api_picks(limit: int = Query(8, ge=1, le=30)):
        return db.top_picks(limit=limit, path=db_path)

    @app.get("/api/listings/{listing_id}")
    def api_listing(listing_id: ListingId):
        item = db.get_listing(listing_id, db_path)
        if item is None:
            raise HTTPException(404, "Объявление не найдено")
        return item

    @app.get("/api/listings/{listing_id}/history")
    def api_history(listing_id: ListingId):
        if db.get_listing(listing_id, db_path) is None:
            raise HTTPException(404, "Объявление не найдено")
        return {"listing_id": listing_id, "points": db.price_series(listing_id, db_path)}

    @app.post("/api/analyze")
    def api_analyze(force: bool = False):
        return start_analyze(db_path, only_missing=not force)

    @app.get("/api/analyze")
    def api_analyze_status():
        return job_status("analyze", db_path)

    @app.post("/api/details")
    def api_details(
        limit: int | None = Query(None, ge=1, le=20000),
        refresh: bool = Query(True, description="Обновить пустые и устаревшие описания"),
    ):
        return start_details(db_path, limit=limit, refresh=refresh)

    @app.get("/api/details")
    def api_details_status():
        return job_status("details", db_path)

    @app.get("/api/advise")
    def api_advise_status():
        return {**advisor_status(), "job": job_status("advise", db_path)}

    @app.post("/api/advise")
    def api_advise(
        limit: int = Query(ADVISE_DEFAULT_LIMIT, ge=1, le=300),
        min_score: float = Query(MIN_UPGRADE_SCORE, ge=0, le=100),
        force: bool = False,
    ):
        return start_advise(
            db_path,
            limit=limit,
            min_score=min_score,
            only_missing=not force,
        )

    @app.post("/api/listings/{listing_id}/advise")
    def api_advise_one(listing_id: ListingId, force: bool = True):
        if db.get_listing(listing_id, db_path) is None:
            raise HTTPException(404, "Объявление не найдено")
        result = advise_candidates(
            path=db_path,
            listing_id=listing_id,
            only_missing=not force,
            limit=1,
        )
        if result.get("error"):
            raise HTTPException(503, result["error"])
        return db.get_listing(listing_id, db_path)

    @app.get("/api/jobs/{kind}/stream")
    async def api_job_stream(kind: str):
        if kind not in KINDS:
            raise HTTPException(404, "Нет такой задачи")

        async def events():
            deadline = time.monotonic() + STREAM_MAX_SEC
            while True:
                st = await run_in_threadpool(job_status, kind, db_path)
                yield f"data: {json.dumps(st, ensure_ascii=False)}\n\n"
                if not st.get("running") or time.monotonic() > deadline:
                    break
                await asyncio.sleep(STREAM_POLL_SEC)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    dist = WEB_DIST if web_dist is None else web_dist
    if dist.exists():
        dist_root = dist.resolve()
        assets = dist_root / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def ui_spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(404, "Нет такого метода API")
            return FileResponse(_dist_file(dist_root, full_path) or dist_root / "index.html")

    return app


def _dist_file(root: Path, rel: str) -> Path | None:
    """Файл из сборки UI. '..', скрытые файлы и выход за корень сборки → None."""
    parts = PurePosixPath(rel).parts
    if not parts or any(part.startswith(".") for part in parts):
        return None
    candidate = (root / rel).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


app = create_app()
