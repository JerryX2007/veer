"""Video handling: saving uploads and cutting per-rally clips with ffmpeg.

Requires ffmpeg to be installed and on PATH (`brew install ffmpeg` /
`apt install ffmpeg`). This is deliberately simple: it shells out to ffmpeg
rather than pulling in a heavier video library, which is plenty for a
personal-scale project.
"""

import subprocess
from pathlib import Path

UPLOAD_DIR = Path("data/videos")
CLIP_DIR = Path("data/clips")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIP_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(filename: str, content: bytes) -> str:
    """Persist an uploaded video and return its path, relative to the backend dir."""
    path = UPLOAD_DIR / filename
    path.write_bytes(content)
    return str(path)


def extract_clip(source_path: str, start_time: float, end_time: float, clip_name: str) -> str:
    """Cut [start_time, end_time] out of source_path into a new clip."""
    out_path = CLIP_DIR / clip_name
    duration = end_time - start_time
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", source_path,
        "-t", str(duration),
        "-c", "copy",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return str(out_path)


def concatenate_clips(clip_paths: list[str], output_name: str) -> str:
    """Join several already-exported clips into one highlight reel."""
    out_path = CLIP_DIR / output_name
    list_file = CLIP_DIR / f"{output_name}.txt"
    list_file.write_text(
        "\n".join(f"file '{Path(p).resolve()}'" for p in clip_paths)
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return str(out_path)
