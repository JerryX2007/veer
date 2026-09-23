"""Finding and tracking the ball with classical computer vision.

1. Candidates: three-frame differencing (pixels that changed both from the
   previous frame and into the next one) isolates where fast-moving objects
   are *now*. Blobs of roughly ball size and shape become candidates.
2. Tracking: candidates are linked frame to frame into tracklets using a
   constant-velocity prediction. Players' heads and hands also make small
   moving blobs, but they don't move fast for long, so slow or short
   tracklets are dropped. Where tracklets overlap in time the longer wins.
3. Short occlusions (the ball hidden behind a player, or blurred at contact)
   are bridged by linear interpolation.

This is the part of the pipeline most sensitive to footage quality. It's
deliberately behind a small interface (`detect_candidates` -> `track_ball`
-> `Trajectory`) so a learned detector can replace it later without
touching rally segmentation or highlight detection.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import AnalysisConfig
from .trajectory import Trajectory

_CLOSE_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
MAX_BALL_SPEED = 40.0  # m/s; faster than any spike, used to reject teleports


@dataclass
class Candidate:
    x: float  # pixels in the analysis frame
    y: float
    radius: float
    score: float  # 0-1, how round/solid the blob is


def to_gray(frame_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (3, 3), 0)


def motion_energy(prev_gray: np.ndarray, gray: np.ndarray) -> float:
    """Mean absolute frame difference: how much is moving overall."""
    return float(cv2.absdiff(prev_gray, gray).mean())


def detect_candidates(
    prev_gray: np.ndarray, gray: np.ndarray, next_gray: np.ndarray, config: AnalysisConfig
) -> list[Candidate]:
    """Ball-like moving blobs in `gray`, the middle of three consecutive frames."""
    height = gray.shape[0]
    th = config.diff_threshold
    moved_in = cv2.absdiff(gray, prev_gray) > th
    moved_out = cv2.absdiff(next_gray, gray) > th
    mask = (moved_in & moved_out).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _CLOSE_KERNEL)

    n, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_r = config.ball_min_radius * height
    max_r = config.ball_max_radius * height
    candidates = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        radius = np.sqrt(area / np.pi)
        if not (min_r <= radius <= max_r):
            continue
        if max(w, h) / max(1, min(w, h)) > config.ball_max_aspect:
            continue
        fill = area / (np.pi * (max(w, h) / 2) ** 2)
        if fill < config.ball_min_fill:
            continue
        cx, cy = centroids[i]
        candidates.append(Candidate(float(cx), float(cy), float(radius), float(min(fill, 1.0))))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[: config.max_candidates_per_frame]


@dataclass
class _Tracklet:
    frames: list[int] = field(default_factory=list)
    xs: list[float] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)
    missed: int = 0

    def add(self, frame: int, c: Candidate) -> None:
        self.frames.append(frame)
        self.xs.append(c.x)
        self.ys.append(c.y)
        self.missed = 0

    def velocity(self) -> tuple[float, float]:
        """Pixels per frame, from the last two detections."""
        if len(self.frames) < 2:
            return 0.0, 0.0
        df = self.frames[-1] - self.frames[-2]
        return (self.xs[-1] - self.xs[-2]) / df, (self.ys[-1] - self.ys[-2]) / df

    def predict(self, frame: int) -> tuple[float, float]:
        vx, vy = self.velocity()
        df = frame - self.frames[-1]
        return self.xs[-1] + vx * df, self.ys[-1] + vy * df

    def median_speed(self) -> float:
        """Pixels per frame."""
        f = np.asarray(self.frames, dtype=float)
        steps = np.hypot(np.diff(self.xs), np.diff(self.ys)) / np.diff(f)
        return float(np.median(steps)) if steps.size else 0.0


def build_tracklets(
    candidates_per_frame: list[list[Candidate]], frame_height: int, max_step: float, config: AnalysisConfig
) -> list[_Tracklet]:
    """`max_step` is the furthest (pixels) the ball can plausibly move in a frame."""
    gate_base = config.track_gate * frame_height
    active: list[_Tracklet] = []
    finished: list[_Tracklet] = []

    for frame, candidates in enumerate(candidates_per_frame):
        pairs = []
        for ti, track in enumerate(active):
            px, py = track.predict(frame)
            df = frame - track.frames[-1]
            if len(track.frames) == 1:
                gate = gate_base + max_step * df  # no velocity yet: anywhere the ball could reach
            else:
                gate = gate_base + 0.5 * np.hypot(*track.velocity()) * df
            for ci, c in enumerate(candidates):
                d = np.hypot(c.x - px, c.y - py)
                if d <= gate:
                    pairs.append((d, ti, ci))
        pairs.sort()

        used_tracks, used_cands = set(), set()
        for _, ti, ci in pairs:
            if ti in used_tracks or ci in used_cands:
                continue
            active[ti].add(frame, candidates[ci])
            used_tracks.add(ti)
            used_cands.add(ci)

        still_active = []
        for ti, track in enumerate(active):
            if ti not in used_tracks:
                track.missed += 1
            if track.missed > config.track_max_missed:
                finished.append(track)
            else:
                still_active.append(track)
        for ci, c in enumerate(candidates):
            if ci not in used_cands:
                t = _Tracklet()
                t.add(frame, c)
                still_active.append(t)
        active = still_active

    return finished + active


def track_ball(
    candidates_per_frame: list[list[Candidate]],
    fps: float,
    frame_width: int,
    frame_height: int,
    config: AnalysisConfig,
) -> Trajectory:
    """Pick the most ball-like tracklets and stitch them into one trajectory."""
    n = len(candidates_per_frame)
    # Speeds in pixels/frame from m/s, using the default scale: the real scale
    # isn't known until we have a trajectory to measure gravity on.
    px_per_m = frame_height / config.default_metres_per_frame_height
    min_speed = config.track_min_speed * px_per_m / fps
    max_step = MAX_BALL_SPEED * px_per_m / fps

    tracklets = [
        t for t in build_tracklets(candidates_per_frame, frame_height, max_step, config)
        if len(t.frames) >= config.track_min_length and t.median_speed() >= min_speed
    ]
    tracklets.sort(key=lambda t: len(t.frames), reverse=True)

    xs = np.full(n, np.nan)
    ys = np.full(n, np.nan)
    for t in tracklets:
        for f, x, y in zip(t.frames, t.xs, t.ys):
            if np.isnan(xs[f]):
                xs[f], ys[f] = x, y

    observed = ~np.isnan(xs)
    _interpolate_gaps(xs, ys, config.max_interp_gap, max_step, frame_height * config.track_gate)
    return Trajectory(
        fps=fps,
        x=xs / frame_height,
        y=ys / frame_height,
        observed=observed,
        aspect=frame_width / frame_height,
    )


def _interpolate_gaps(xs: np.ndarray, ys: np.ndarray, max_gap: int, max_step: float, slack: float) -> None:
    known = np.flatnonzero(~np.isnan(xs))
    for a, b in zip(known[:-1], known[1:]):
        gap = b - a
        if gap <= 1 or gap - 1 > max_gap:
            continue
        if np.hypot(xs[b] - xs[a], ys[b] - ys[a]) > max_step * gap + slack:
            continue  # a jump between two different objects, not an occlusion
        frac = np.arange(1, gap) / gap
        xs[a + 1:b] = xs[a] + (xs[b] - xs[a]) * frac
        ys[a + 1:b] = ys[a] + (ys[b] - ys[a]) * frac


