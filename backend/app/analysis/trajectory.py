"""The ball's path through a match, and the physics we read off it.

Positions are in frame heights (so x and y share a unit), with y pointing
down as in the image. A *contact* is any moment the ball's velocity changes
more abruptly than gravity allows: a hand, a block, the floor. Between
contacts the ball is in free flight, and fitting parabolas to those flights
tells us how many pixels a metre is (gravity is always 9.81 m/s^2).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

GRAVITY = 9.81  # m/s^2
MAX_FLIGHT_RESIDUAL = 0.004  # frame heights; noisier fits aren't clean flights
PLAUSIBLE_METRES_PER_FRAME_HEIGHT = (2.0, 60.0)


@dataclass
class Trajectory:
    fps: float
    x: np.ndarray  # frame heights from the left edge, NaN where unknown
    y: np.ndarray  # frame heights from the top edge (down is positive)
    observed: np.ndarray  # True where the ball was detected, not interpolated
    aspect: float  # frame width / frame height

    @property
    def n(self) -> int:
        return self.x.size

    @property
    def known(self) -> np.ndarray:
        return ~np.isnan(self.x)

    def time(self, index: int) -> float:
        return index / self.fps

    def index(self, time: float) -> int:
        return int(np.clip(round(time * self.fps), 0, max(0, self.n - 1)))

    def coverage(self) -> float:
        return float(self.observed.mean()) if self.n else 0.0

    def speed(self) -> np.ndarray:
        """Frame heights per second at each frame (NaN where unknown)."""
        speed = np.full(self.n, np.nan)
        if self.n >= 3:
            dx = self.x[2:] - self.x[:-2]
            dy = self.y[2:] - self.y[:-2]
            speed[1:-1] = np.hypot(dx, dy) * self.fps / 2
        return speed


@dataclass
class Contact:
    index: int
    time: float
    x: float  # frame heights
    y: float
    v_in: tuple[float, float]  # (vx, vy) frame heights / s just before
    v_out: tuple[float, float]  # ... and just after
    dv: float  # velocity change not explained by gravity, frame heights / s

    @property
    def bounces_up(self) -> bool:
        """Was falling, now rising: a dig, a pass or the floor."""
        return self.v_in[1] > 0 and self.v_out[1] < 0

    def speed_in(self) -> float:
        return float(np.hypot(*self.v_in))


def _window_fit(v: np.ndarray, w: np.ndarray, lo: int, hi: int, fps: float):
    """Least-squares slope of v over the frames [i+lo, i+hi], for every i.

    Samples with weight 0 are ignored. Returns (slope per second, mean time
    offset of the samples used, in seconds relative to frame i); slope is NaN
    where fewer than 3 samples fall in the window. Offsets are kept relative
    to i so the sums stay small and precise even hours into a match.
    """
    n = v.size
    vz = np.where(w > 0, v, 0.0)
    s_w, s_k, s_kk, s_v, s_kv = (np.zeros(n) for _ in range(5))
    for k in range(lo, hi + 1):
        src = slice(max(0, k), min(n, n + k))
        dst = slice(max(0, -k), min(n, n - k))
        wk, vk = w[src], vz[src]
        s_w[dst] += wk
        s_k[dst] += k * wk
        s_kk[dst] += k * k * wk
        s_v[dst] += wk * vk
        s_kv[dst] += k * wk * vk
    with np.errstate(invalid="ignore", divide="ignore"):
        denom = s_w * s_kk - s_k * s_k
        slope = (s_w * s_kv - s_k * s_v) / denom * fps
        mean_offset = s_k / s_w / fps
    slope[(s_w < 3) | (np.abs(denom) < 1e-9)] = np.nan
    return slope, mean_offset


def find_contacts(
    traj: Trajectory, gravity: float, min_dv: float, window_s: float
) -> list[Contact]:
    """Moments where the ball's velocity jumps by more than `min_dv` (fh/s).

    `gravity` is in frame heights / s^2 and is subtracted from the vertical
    velocity change, so a ball simply falling faster isn't a contact.
    """
    if traj.n < 3:
        return []
    half = max(3, int(round(window_s * traj.fps)))
    fps = traj.fps
    t = np.arange(traj.n) / fps
    w = traj.observed.astype(float)

    vx_in, tc_in = _window_fit(traj.x, w, -half, 0, fps)
    vy_in, _ = _window_fit(traj.y, w, -half, 0, fps)
    vx_out, tc_out = _window_fit(traj.x, w, 0, half, fps)
    vy_out, _ = _window_fit(traj.y, w, 0, half, fps)

    with np.errstate(invalid="ignore"):
        dv = np.hypot(vx_out - vx_in, (vy_out - vy_in) - gravity * (tc_out - tc_in))
    dv[~traj.known] = np.nan

    order = np.argsort(np.nan_to_num(dv, nan=-1.0))[::-1]
    taken = np.zeros(traj.n, dtype=bool)
    contacts = []
    for i in order:
        if not dv[i] >= min_dv:
            break
        if taken[max(0, i - half):i + half + 1].any():
            continue
        taken[i] = True
        contacts.append(Contact(
            index=int(i),
            time=float(t[i]),
            x=float(traj.x[i]),
            y=float(traj.y[i]),
            v_in=(float(vx_in[i]), float(vy_in[i])),
            v_out=(float(vx_out[i]), float(vy_out[i])),
            dv=float(dv[i]),
        ))
    contacts.sort(key=lambda c: c.index)
    _refine_contacts(traj, contacts, half, gravity, min_dv)
    return contacts


def _refine_contacts(
    traj: Trajectory, contacts: list[Contact], half: int, gravity: float, min_dv: float
) -> None:
    """Pin down each contact's frame, then re-measure v_in / v_out.

    The first pass smears contacts that are close together (an attack
    straight into a block is shorter than the detection window). Here each
    contact moves to the frame where a straight line before it and one after
    it fit best (while still being a real change of velocity), and the fits
    never reach past a neighbouring contact.
    """
    shift = max(1, half // 2)
    for k, c in enumerate(contacts):
        prev_i = contacts[k - 1].index if k > 0 else -1
        next_i = contacts[k + 1].index if k + 1 < len(contacts) else traj.n
        best, best_cost = c.index, np.inf
        for j in range(max(prev_i + 1, c.index - shift), min(next_i, c.index + shift + 1)):
            before, after = _fit(traj, prev_i, j, half, -1), _fit(traj, next_i, j, half, 1)
            if not (before and after):
                continue
            (vx_in, vy_in), cost_in, t_in = before
            (vx_out, vy_out), cost_out, t_out = after
            dv = np.hypot(vx_out - vx_in, (vy_out - vy_in) - gravity * (t_out - t_in))
            if dv >= min_dv and cost_in + cost_out < best_cost:
                best, best_cost = j, cost_in + cost_out
        if best_cost == np.inf:
            continue
        before, after = _fit(traj, prev_i, best, half, -1), _fit(traj, next_i, best, half, 1)
        c.index, c.time = best, best / traj.fps
        if traj.known[best]:
            c.x, c.y = float(traj.x[best]), float(traj.y[best])
        c.v_in, c.v_out = before[0], after[0]


def _fit(traj: Trajectory, limit: int, i: int, half: int, direction: int):
    """Line fit of the observed samples on one side of frame i.

    Uses up to `half` frames, stopping short of the neighbouring contact at
    `limit`. Returns ((vx, vy) per second, squared error, mean sample time)
    or None when there are fewer than 3 samples.
    """
    if direction < 0:
        idx = np.arange(max(limit + 1, i - half, 0), i + 1)
    else:
        idx = np.arange(i, min(limit, i + half + 1, traj.n))
    idx = idx[traj.observed[idx]]
    if idx.size < 3:
        return None
    t = idx / traj.fps
    (vx, x0), (vy, y0) = np.polyfit(t, traj.x[idx], 1), np.polyfit(t, traj.y[idx], 1)
    cost = np.sum((traj.x[idx] - (vx * t + x0)) ** 2 + (traj.y[idx] - (vy * t + y0)) ** 2)
    return (float(vx), float(vy)), float(cost), float(t.mean())


def estimate_gravity(traj: Trajectory, contacts: list[Contact], min_flights: int) -> Optional[float]:
    """Median downward acceleration of clean free-flight arcs, in fh / s^2.

    Returns None when there aren't enough clean arcs to trust the estimate.
    """
    min_len = max(8, int(round(0.3 * traj.fps)))
    trim = 2
    breaks = {c.index for c in contacts}

    pieces, current = [], []
    for i in range(traj.n):
        if not traj.observed[i] or i in breaks:
            if len(current) >= min_len + 2 * trim:
                pieces.append(current[trim:-trim])
            current = []
            continue
        current.append(i)
    if len(current) >= min_len + 2 * trim:
        pieces.append(current[trim:-trim])

    estimates = []
    for piece in pieces:
        idx = np.asarray(piece)
        t = idx / traj.fps
        y_fit = np.polyfit(t, traj.y[idx], 2)
        x_fit = np.polyfit(t, traj.x[idx], 1)
        y_res = traj.y[idx] - np.polyval(y_fit, t)
        x_res = traj.x[idx] - np.polyval(x_fit, t)
        if np.sqrt(np.mean(y_res ** 2)) > MAX_FLIGHT_RESIDUAL:
            continue
        if np.sqrt(np.mean(x_res ** 2)) > MAX_FLIGHT_RESIDUAL:
            continue
        g = 2 * y_fit[0]
        if g <= 0:
            continue
        low, high = PLAUSIBLE_METRES_PER_FRAME_HEIGHT
        if low <= GRAVITY / g <= high:
            estimates.append(g)

    if len(estimates) < min_flights:
        return None
    return float(np.median(estimates))
