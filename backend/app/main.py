from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models
from .database import engine
from .routers import highlights, matches, rallies

models.Base.metadata.create_all(bind=engine)

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


@app.get("/")
def root():
    return {"status": "ok"}
