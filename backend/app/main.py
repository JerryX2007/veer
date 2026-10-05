import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .config import settings
from .media import jobs
from .routers import analysis, matches, rallies, reels
from .services.analysis_jobs import mark_interrupted_runs


@asynccontextmanager
async def lifespan(_: FastAPI):
    for binary in (settings.ffmpeg_bin, settings.ffprobe_bin):
        if shutil.which(binary) is None:
            raise RuntimeError(f"{binary} not found on PATH. Install ffmpeg (https://ffmpeg.org/download.html).")
    settings.ensure_dirs()
    db.init_engine()
    with db.SessionLocal() as session:
        mark_interrupted_runs(session)
    yield
    jobs.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title="Volleyball Highlights", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server for the React frontend
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(matches.router)
    app.include_router(rallies.router)
    app.include_router(reels.router)
    app.include_router(analysis.router)
    # Serves match videos, clips, thumbnails and reels (supports Range requests, so <video> can seek).
    settings.media_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

    @app.get("/health", tags=["meta"])
    def health():
        return {"ok": True}

    return app


app = create_app()
