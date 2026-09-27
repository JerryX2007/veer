"""Thin, testable wrappers around the ffmpeg / ffprobe binaries."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from ..config import settings


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], *, binary: str | None = None) -> str:
    cmd = [binary or settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFmpegError(f"{' '.join(cmd[:1])} failed ({proc.returncode}): {proc.stderr.strip()[-2000:]}")
    return proc.stdout


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    video_codec: str


def probe(path: Path | str) -> VideoInfo:
    proc = subprocess.run(
        [settings.ffprobe_bin, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe could not read {path}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise FFmpegError(f"{path} has no video stream")

    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    try:
        fps = float(Fraction(rate)) if rate != "0/0" else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)

    # Phones record portrait video with a rotation flag; report the displayed size.
    width, height = int(video["width"]), int(video["height"])
    rotation = 0
    for side in video.get("side_data_list", []) or []:
        if "rotation" in side:
            rotation = abs(int(side["rotation"]))
    if rotation in (90, 270):
        width, height = height, width

    return VideoInfo(
        duration=duration,
        width=width,
        height=height,
        fps=round(fps, 3),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        video_codec=video.get("codec_name", "unknown"),
    )
