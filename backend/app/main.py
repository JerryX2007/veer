import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

<<<<<<< Updated upstream
from . import models
from .database import SessionLocal, engine
from .routers import analysis, highlights, matches, rallies
from .services.analysis_jobs import mark_interrupted_runs

models.Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    mark_interrupted_runs(db)

app = FastAPI(title="Volleyball Rally Tagger & Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded videos and exported clips directly, e.g. GET /data/videos/x.mp4
app.mount("/data", StaticFiles(directory="data"), name="data")

app.include_router(matches.router)
app.include_router(rallies.router)
app.include_router(highlights.router)
app.include_router(analysis.router)
=======
from . import db
from .config import settings
from .media import jobs
from .routers import matches, rallies, reels
>>>>>>> Stashed changes


@asynccontextmanager
async def lifespan(_: FastAPI):
    for binary in (settings.ffmpeg_bin, settings.ffprobe_bin):
        if shutil.which(binary) is None:
            raise RuntimeError(f"{binary} not found on PATH. Install ffmpeg (https://ffmpeg.org/download.html).")
    settings.ensure_dirs()
    db.init_engine()
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
    # Serves match videos, clips, thumbnails and reels (supports Range requests, so <video> can seek).
    settings.media_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

    @app.get("/health", tags=["meta"])
    def health():
        return {"ok": True}

    return app


app = create_app()
