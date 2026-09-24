"""analyze_video: from a match file to rallies, highlights and a reel.

    audio  ─> crowd loudness, whistles ───────────────────┐
    frames ─> ball candidates ─> ball trajectory ─> contacts ─> rallies ─> highlights ─> reel
          └─> overall motion (fallback for rallies) ──┘

One decoding pass over the video at up to 30 fps and 640 px wide; everything
after that works on small arrays.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

from .audio import AudioSignals, analyze_audio
from .ball import detect_candidates, motion_energy, to_gray, track_ball
from .config import AnalysisConfig
from .highlights import Highlight, detect_highlights
from .media import analysis_size, iter_frames, probe, read_audio
from .rallies import Rally, segment_rallies
from .reel import Reel, build_reel
from .trajectory import GRAVITY, Trajectory, estimate_gravity, find_contacts

AUDIO_RATE = 16000
ProgressCallback = Callable[[float], None]


@dataclass
class AnalysisResult:
    duration: float
    rallies: list[Rally]
    highlights: list[Highlight]
    reel: Reel
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration": round(self.duration, 2),
            "rallies": [
                {
                    "index": r.index,
                    "start": r.start,
                    "end": r.end,
                    "serve_time": r.serve_time,
                    "play_start": r.play_start,
                    "play_end": r.play_end,
                    "contacts": len(r.contacts),
                }
                for r in self.rallies
            ],
            "highlights": [
                {
                    "kind": h.kind,
                    "label": h.label,
                    "time": h.time,
                    "score": h.score,
                    "rally_index": h.rally_index,
                    "description": h.description,
                    "details": h.details,
                }
                for h in self.highlights
            ],
            "reel": self.reel.to_dict(),
            "diagnostics": self.diagnostics,
        }


def calibrate(traj: Trajectory, config: AnalysisConfig):
    """Contacts, plus metres per frame height measured from gravity if possible."""
    metres = config.default_metres_per_frame_height
    contacts = find_contacts(traj, GRAVITY / metres, config.contact_min_dv / metres, config.contact_window)
    gravity = estimate_gravity(traj, contacts, config.gravity_min_flights)
    if gravity is None:
        return contacts, metres, False
    metres = GRAVITY / gravity
    contacts = find_contacts(traj, gravity, config.contact_min_dv / metres, config.contact_window)
    return contacts, metres, True


def analyze_video(
    path: str,
    config: Optional[AnalysisConfig] = None,
    progress: Optional[ProgressCallback] = None,
) -> AnalysisResult:
    config = config or AnalysisConfig()
    report = progress or (lambda _: None)
    info = probe(path)
    fps = min(config.analysis_fps, info.fps)
    width, height = analysis_size(info, config.analysis_width)

    audio = AudioSignals()
    if info.has_audio:
        audio = analyze_audio(read_audio(path, AUDIO_RATE), AUDIO_RATE)
    report(0.02)

    expected = max(1, int(info.duration * fps))
    grays: deque = deque(maxlen=3)
    candidates: list = [[]]  # frame 0 has no previous frame to diff against
    motion: list[float] = []
    for i, frame in enumerate(iter_frames(path, fps, width, height)):
        gray = to_gray(frame)
        motion.append(motion_energy(grays[-1], gray) if grays else 0.0)
        grays.append(gray)
        if len(grays) == 3:
            candidates.append(detect_candidates(grays[0], grays[1], grays[2], config))
        if i % 150 == 0:
            report(0.02 + 0.93 * min(1.0, i / expected))
    n = len(motion)
    candidates = (candidates + [[]])[:n]  # the last frame has no next frame either
    duration = info.duration or n / fps

    traj = track_ball(candidates, fps, width, height, config)
    contacts, metres_per_fh, calibrated = calibrate(traj, config)
    rallies, rally_source = segment_rallies(
        traj, contacts, np.asarray(motion), audio.whistles, duration, metres_per_fh, config
    )
    highlights = detect_highlights(rallies, traj, audio, metres_per_fh, config)
    reel = build_reel(rallies, highlights, config.reel_min_score)
    report(1.0)

    diagnostics = {
        "frames_analyzed": n,
        "analysis_fps": round(fps, 3),
        "analysis_size": [width, height],
        "ball_coverage": round(traj.coverage(), 3),
        "contacts": len(contacts),
        "metres_per_frame_height": round(metres_per_fh, 2),
        "scale_calibrated": calibrated,
        "rally_source": rally_source,
        "has_audio": audio.available,
        "whistles": [round(start, 2) for start, _ in audio.whistles],
    }
    return AnalysisResult(duration, rallies, highlights, reel, diagnostics)
