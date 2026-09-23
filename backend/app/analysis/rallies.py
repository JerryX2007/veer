"""Splitting a match into rallies, each running from the serve to a dead ball.

A rally is a stretch where the ball keeps moving at playing speed, with no
pause longer than `rally_max_gap`. Its clip starts shortly before the serve
(so the toss is included) and ends shortly after the ball goes dead, stretched
to take in the referee's whistle if one follows closely.

The serve is the hit that first sends the ball over the net at speed. Early
in a segment the server may bounce the ball before serving; the clip skips
that and starts at the serve.

If the ball tracker found almost nothing (poor footage), rallies fall back to
bursts of overall on-screen motion. Those clips are rougher and have no serve
time, but crowd-reaction and long-rally highlights still work on them.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .config import AnalysisConfig
from .trajectory import Contact, Trajectory

SERVE_SEARCH_WINDOW = 4.0  # s after play starts that a serve can be
WHISTLE_TAIL = 0.3  # s kept after a whistle that ends a rally


@dataclass
class Rally:
    index: int
    start: float  # clip start: serve minus pre-roll (seconds into the video)
    end: float  # clip end: dead ball plus post-roll
    play_start: float  # first ball activity
    play_end: float  # last ball activity
    serve_time: Optional[float] = None
    contacts: list[Contact] = field(default_factory=list)

    @property
    def rally_length(self) -> float:
        """Seconds of actual play, from the serve (if seen) to the dead ball."""
        start = self.serve_time if self.serve_time is not None else self.play_start
        return self.play_end - start


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (first, last) index pairs of consecutive True values."""
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(a), int(b) - 1) for a, b in zip(edges[::2], edges[1::2])]


def _merge(runs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for a, b in runs:
        if merged and a - merged[-1][1] - 1 <= max_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def _find_serve(
    traj: Trajectory, contacts: list[Contact], first: int, last: int,
    speed_ms: np.ndarray, config: AnalysisConfig,
) -> Optional[float]:
    net = config.net_x * traj.aspect
    fps = traj.fps
    search_end = min(last, first + int(SERVE_SEARCH_WINDOW * fps))
    for i in range(first, search_end):
        a, b = traj.x[i] - net, traj.x[i + 1] - net
        if np.isnan(a) or np.isnan(b) or a * b > 0:
            continue
        if not speed_ms[i] >= config.serve_min_speed:
            continue
        lookback = i - int(config.serve_lookback * fps)
        hits = [c for c in contacts if lookback <= c.index < i]
        if hits:
            return hits[-1].time
        # The hit itself wasn't seen: start from where this flight was picked up.
        j = i
        while j > max(first, lookback) and traj.known[j - 1]:
            j -= 1
        return traj.time(j)
    return None


def _ball_segments(traj: Trajectory, speed_ms: np.ndarray, config: AnalysisConfig):
    active = traj.known & (np.nan_to_num(speed_ms) >= config.active_min_speed)
    max_gap = int(config.rally_max_gap * traj.fps)
    return _merge(_runs(active), max_gap)


def _motion_segments(motion: np.ndarray, fps: float, config: AnalysisConfig):
    if motion.size == 0:
        return []
    k = max(1, int(fps))
    smooth = np.convolve(motion, np.ones(k) / k, mode="same")
    high, low = np.percentile(smooth, 70), np.percentile(smooth, 50)
    active = np.zeros(smooth.size, dtype=bool)
    on = False
    for i, v in enumerate(smooth):  # hysteresis: enter above `high`, leave below `low`
        on = v >= high if not on else v >= low
        active[i] = on
    return _merge(_runs(active), int(config.rally_max_gap * fps))


def segment_rallies(
    traj: Trajectory,
    contacts: list[Contact],
    motion: np.ndarray,
    whistles: list[tuple[float, float]],
    duration: float,
    metres_per_fh: float,
    config: AnalysisConfig,
) -> tuple[list[Rally], str]:
    """Returns the rallies and which signal found them ("ball" or "motion")."""
    fps = traj.fps
    speed_ms = traj.speed() * metres_per_fh
    use_ball = traj.coverage() >= config.motion_fallback_coverage
    if use_ball:
        segments = _ball_segments(traj, speed_ms, config)
    else:
        segments = _motion_segments(motion, fps, config)

    rallies: list[Rally] = []
    for first, last in segments:
        play_start, play_end = first / fps, last / fps
        if play_end - play_start < config.rally_min_duration:
            continue

        serve = _find_serve(traj, contacts, first, last, speed_ms, config) if use_ball else None
        start = (serve if serve is not None else play_start) - config.serve_preroll
        end = play_end + config.rally_postroll
        for w_start, w_end in whistles:
            if play_end <= w_start <= play_end + config.whistle_end_window:
                end = max(end, w_end + WHISTLE_TAIL)
                break

        start = max(0.0, start, rallies[-1].end if rallies else 0.0)
        end = min(duration, end) if duration > 0 else end
        rallies.append(Rally(
            index=len(rallies),
            start=round(start, 2),
            end=round(end, 2),
            play_start=round(play_start, 2),
            play_end=round(play_end, 2),
            serve_time=round(serve, 2) if serve is not None else None,
            contacts=[c for c in contacts if start <= c.time <= end],
        ))
    return rallies, "ball" if use_ball else "motion"
