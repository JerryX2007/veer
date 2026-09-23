"""Reading video frames and audio samples out of a match file via ffmpeg.

Frames are decoded and resampled by ffmpeg itself (`fps` + `scale` filters)
and piped in as raw BGR bytes. Letting ffmpeg resample to a constant frame
rate means frame i is always at exactly i / fps seconds, even for phone
footage recorded at a variable frame rate.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator

import numpy as np


class MediaError(RuntimeError):
    pass


@dataclass
class VideoInfo:
    width: int  # as displayed, i.e. after applying rotation metadata
    height: int
    fps: float
    duration: float
    has_audio: bool


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise MediaError(f"{tool} not found - install ffmpeg and make sure it's on your PATH")
    return path


def probe(path: str) -> VideoInfo:
    cmd = [
        _require("ffprobe"), "-v", "error",
        "-show_streams", "-show_format", "-of", "json", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise MediaError(f"ffprobe couldn't read {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError(f"{path} has no video stream")

    width, height = int(video["width"]), int(video["height"])
    rotation = int(float(video.get("tags", {}).get("rotate", 0)))
    for side_data in video.get("side_data_list", []):
        if "rotation" in side_data:
            rotation = int(float(side_data["rotation"]))
    if abs(rotation) % 180 == 90:
        width, height = height, width

    fps = 0.0
    for key in ("avg_frame_rate", "r_frame_rate"):
        rate = video.get(key, "0/0")
        if rate and not rate.startswith("0/") and rate != "0/0":
            fps = float(Fraction(rate))
            break
    if fps <= 0:
        fps = 30.0

    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0.0)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return VideoInfo(width, height, fps, duration, has_audio)


def analysis_size(info: VideoInfo, target_width: int) -> tuple[int, int]:
    """Downscaled (width, height), both even, never upscaling."""
    width = min(target_width, info.width)
    width -= width % 2
    height = int(round(width * info.height / info.width / 2)) * 2
    return width, max(height, 2)


def iter_frames(path: str, fps: float, width: int, height: int) -> Iterator[np.ndarray]:
    """Yield BGR frames (height x width x 3, uint8) at a constant `fps`."""
    cmd = [
        _require("ffmpeg"), "-v", "error", "-nostdin",
        "-i", path, "-an", "-sn",
        "-vf", f"fps={fps},scale={width}:{height}",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
    ]
    frame_bytes = width * height * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            yield np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)
    finally:
        proc.stdout.close()
        stderr = proc.stderr.read().decode(errors="replace")
        proc.stderr.close()
        returncode = proc.wait()
    if returncode != 0:
        raise MediaError(f"ffmpeg failed decoding {path}: {stderr.strip()}")


def read_audio(path: str, sample_rate: int = 16000) -> np.ndarray:
    """Mono float32 samples in [-1, 1]. Empty if the file has no audio."""
    cmd = [
        _require("ffmpeg"), "-v", "error", "-nostdin",
        "-i", path, "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-f", "s16le", "-",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise MediaError(f"ffmpeg failed reading audio from {path}: {result.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
