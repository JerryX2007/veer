"""Cut rallies out of match footage and render reels.

Every clip is encoded to one "house format" (H.264 yuv420p, fixed fps, AAC stereo 48 kHz, always with an
audio track). That costs a re-encode per clip, but buys two things:
  * frame-accurate cuts (stream-copy can only cut on keyframes, often seconds off), and
  * reels that concatenate with `-c copy`, i.e. instantly, when clips share a resolution.
"""
from __future__ import annotations

import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from . import ffmpeg

MAX_WIDTH = 1920


@dataclass(frozen=True)
class Window:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def padded_window(start: float, end: float, source_duration: float,
                  pad_before: float | None = None, pad_after: float | None = None) -> Window:
    if end <= start:
        raise ValueError(f"rally end ({end}) must be after start ({start})")
    pb = settings.clip_pad_before if pad_before is None else pad_before
    pa = settings.clip_pad_after if pad_after is None else pad_after
    s = max(0.0, start - pb)
    e = min(source_duration, end + pa) if source_duration > 0 else end + pa
    if e <= s:
        raise ValueError(f"rally {start}-{end}s is outside the video (duration {source_duration}s)")
    return Window(round(s, 3), round(e, 3))


def _video_filter(width: int | None = None, height: int | None = None) -> str:
    fps = settings.clip_fps
    if width and height:
        # Letterbox into a fixed frame (used when a reel mixes resolutions).
        return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p")
    # Keep source size (capped), forced to even dimensions for yuv420p.
    return f"scale='min({MAX_WIDTH},iw)':-2,setsar=1,fps={fps},format=yuv420p"


def _encode_args() -> list[str]:
    return [
        "-c:v", "libx264", "-preset", settings.clip_preset, "-crf", str(settings.clip_crf),
        "-c:a", "aac", "-b:a", "128k", "-ar", str(settings.clip_audio_rate), "-ac", "2",
        "-movflags", "+faststart",
    ]


def cut_clip(source: Path, window: Window, out: Path, *, source_has_audio: bool) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    args = ["-ss", f"{window.start:.3f}", "-t", f"{window.duration:.3f}", "-i", str(source)]
    if source_has_audio:
        maps = ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        # Silent track keeps every clip's stream layout identical, so reels can stream-copy.
        args += ["-f", "lavfi", "-t", f"{window.duration:.3f}",
                 "-i", f"anullsrc=r={settings.clip_audio_rate}:cl=stereo"]
        maps = ["-map", "0:v:0", "-map", "1:a:0"]
    tmp = out.with_suffix(".part.mp4")
    ffmpeg.run([*args, *maps, "-vf", _video_filter(), *_encode_args(), "-shortest", str(tmp)])
    tmp.replace(out)  # atomic: a half-written clip is never visible at `out`
    return out


def thumbnail(clip: Path, at: float, out: Path, width: int = 480) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(["-ss", f"{max(0.0, at):.3f}", "-i", str(clip), "-frames:v", "1",
                "-vf", f"scale={width}:-2", "-q:v", "3", str(out)])
    return out


def concat_reel(clips: list[Path], out: Path) -> Path:
    """Join clips into one video. Stream-copies when all clips share a size, else re-encodes to the most common one."""
    if not clips:
        raise ValueError("a reel needs at least one clip")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.mp4")

    sizes = [(i.width, i.height) for i in (ffmpeg.probe(c) for c in clips)]
    if len(set(sizes)) == 1:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            for c in clips:
                escaped = str(Path(c).resolve()).replace("'", r"'\''")
                f.write(f"file '{escaped}'\n")
            listfile = f.name
        try:
            ffmpeg.run(["-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy",
                        "-movflags", "+faststart", str(tmp)])
        finally:
            Path(listfile).unlink(missing_ok=True)
    else:
        w, h = Counter(sizes).most_common(1)[0][0]
        inputs: list[str] = []
        for c in clips:
            inputs += ["-i", str(c)]
        vf = _video_filter(w, h)
        parts = [f"[{i}:v]{vf}[v{i}];[{i}:a]aresample={settings.clip_audio_rate}[a{i}];" for i in range(len(clips))]
        chain = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
        graph = "".join(parts) + f"{chain}concat=n={len(clips)}:v=1:a=1[v][a]"
        ffmpeg.run([*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", *_encode_args(), str(tmp)])

    tmp.replace(out)
    return out
