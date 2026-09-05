"""HTTP API над локальной БД. Поиск и апгрейд не ходят на skelbiu.lt."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from skelbiu_pc import db
from skelbiu_pc.advisors import advisor_status
from skelbiu_pc.config import ADVISE_DEFAULT_LIMIT, MIN_UPGRADE_SCORE, ROOT
from skelbiu_pc.sources import list_sources
from skelbiu_pc.jobs import start as start_analyze
from skelbiu_pc.jobs import start_advise, start_details
from skelbiu_pc.jobs import status as job_status
from skelbiu_pc.pipeline import advise_candidates

WEB_DIST = ROOT / "web" / "dist"


def create_app(db_path: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_db(db_path)
        yield

    app = FastAPI(title="Skelbiu PC", version="0.4.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        q: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        city: str | None = None,
        socket: str | None = None,
        source: str | None = None,
        potential: bool | None = None,
        kind: str = Query("desktop", pattern="^(all|desktop|laptop)$"),
        sort: str = Query(
            "score",
            pattern="^(score|price_asc|price_desc|seen|title|profit|resale|cost|ai)$",
        ),
        page: int = Query(1, ge=1),
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
            kind=kind,
            sort=sort,
            page=page,
            limit=limit,
            path=db_path,
        )

    @app.get("/api/listings/{listing_id}")
    def api_listing(listing_id: str):
        item = db.get_listing(listing_id, db_path)
        if item is None:
            raise HTTPException(404, "Объявление не найдено")
        return item

    @app.get("/api/listings/{listing_id}/history")
    def api_history(listing_id: str):
        if db.get_listing(listing_id, db_path) is None:
            raise HTTPException(404, "Объявление не найдено")
        return {"listing_id": listing_id, "points": db.price_series(listing_id, db_path)}

    @app.post("/api/analyze")
    def api_analyze(force: bool = False):
        return start_analyze(db_path, only_missing=not force)

    @app.get("/api/analyze")
    def api_analyze_status():
        return job_status("analyze")

    @app.post("/api/details")
    def api_details(limit: int | None = Query(None, ge=1, le=20000)):
        return start_details(db_path, limit=limit)

    @app.get("/api/details")
    def api_details_status():
        return job_status("details")

    @app.get("/api/advise")
    def api_advise_status():
        return {**advisor_status(), "job": job_status("advise")}

    @app.post("/api/advise")
    def api_advise(
        limit: int = Query(ADVISE_DEFAULT_LIMIT, ge=1, le=300),
        min_score: float = Query(MIN_UPGRADE_SCORE, ge=0),
        force: bool = False,
    ):
        return start_advise(
            db_path,
            limit=limit,
            min_score=min_score,
            only_missing=not force,
        )

    @app.post("/api/listings/{listing_id}/advise")
    def api_advise_one(listing_id: str, force: bool = True):
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

    if WEB_DIST.exists():
        assets = WEB_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def ui_index():
            return FileResponse(WEB_DIST / "index.html")

        @app.get("/{full_path:path}")
        def ui_spa(full_path: str):
            candidate = WEB_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app


app = create_app()
