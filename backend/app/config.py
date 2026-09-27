"""App settings. Override any of these with environment variables prefixed VB_ (e.g. VB_MEDIA_ROOT)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VB_", env_file=".env", extra="ignore")

    media_root: Path = Path("data/media")
    database_url: str = "sqlite:///data/volleyball.db"

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    # Seconds added before a tagged rally start / after its end, so clips don't feel clipped.
    clip_pad_before: float = 1.0
    clip_pad_after: float = 1.5

    # Encoding used for every clip. Keeping clips uniform lets reels concatenate without re-encoding.
    clip_crf: int = 20
    clip_preset: str = "veryfast"
    clip_fps: int = 30
    clip_audio_rate: int = 48000

    # Background job workers. Set VB_SYNC_JOBS=true to run jobs inline (tests, debugging).
    job_workers: int = 2
    sync_jobs: bool = False

    @property
    def uploads_dir(self) -> Path:
        return self.media_root / "uploads"

    @property
    def clips_dir(self) -> Path:
        return self.media_root / "clips"

    @property
    def thumbs_dir(self) -> Path:
        return self.media_root / "thumbs"

    @property
    def reels_dir(self) -> Path:
        return self.media_root / "reels"

    def ensure_dirs(self) -> None:
        for d in (self.uploads_dir, self.clips_dir, self.thumbs_dir, self.reels_dir):
            d.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
