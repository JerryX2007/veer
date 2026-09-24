"""Spotting the moments worth a highlight reel inside each rally.

Every detector reads the rally's contacts (see `trajectory.find_contacts`),
converted to metres with the calibrated scale:

- big_kill: an attack hits the floor and the ball rebounds high. The landing
  is the first steep, fast, falling-then-rising contact that nobody plays on
  from (the next rising contact, if any, is another bounce at floor level
  rather than a player a metre or more above it), close to the end of play.
- great_save: the same kind of hard-driven ball dug back up, but the rally
  carries on: the next rising contact is a player well above the dig.
- shutdown_block: a fast ball driven at the net is sent back where it came
  from, lands on the attacker's side, and the rally dies.
- crowd_reaction: the crowd gets loud right after the rally.
- long_rally: play lasts much longer than a typical rally.

Every detected highlight scores between 0.5 (just over the threshold) and
1.0 (a standout), plus a small boost when the crowd reacts.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .audio import AudioSignals
from .config import AnalysisConfig
from .rallies import Rally
from .trajectory import Contact, Trajectory

KIND_LABELS = {
    "big_kill": "Big kill",
    "great_save": "Great save",
    "shutdown_block": "Shutdown block",
    "crowd_reaction": "Crowd reaction",
    "long_rally": "Long rally",
}
PLAYER_ABOVE_FLOOR = 1.2  # m: a rising contact this far above a dig is a player
FOLLOW_UP_WINDOW = 3.0  # s to look for the contact after a dig or landing
REBOUND_WINDOW = 2.5  # s to watch the ball climb after a landing
TOP_EDGE = 0.03  # frame heights; a track ending here left through the top
SERVE_RECEIVE_DELAY = 0.3  # s; the first rising contact after this is the pass


@dataclass
class Highlight:
    kind: str
    time: float  # the moment itself, seconds into the video
    score: float
    rally_index: int
    description: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind.replace("_", " ").capitalize())


def _ramp(value: float, lo: float, hi: float) -> float:
    """0.5 at the threshold `lo`, rising to 1.0 at `hi`."""
    if hi <= lo:
        return 1.0
    return 0.5 + 0.5 * float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


class _RallyContext:
    """A rally's contacts in metres, plus helpers the detectors share."""

    def __init__(self, rally: Rally, traj: Trajectory, metres_per_fh: float, config: AnalysisConfig):
        self.rally = rally
        self.traj = traj
        self.m = metres_per_fh
        self.config = config
        self.contacts = rally.contacts
        self.net = config.net_x * traj.aspect

    def speed_in(self, c: Contact) -> float:
        return c.speed_in() * self.m

    def is_hard_falling_bounce(self, c: Contact, min_speed: float) -> bool:
        speed = self.speed_in(c)
        return (
            c.bounces_up
            and speed >= min_speed
            and c.v_in[1] * self.m >= self.config.attack_min_steepness * speed
        )

    def next_rising(self, c: Contact) -> Optional[Contact]:
        for other in self.contacts:
            if c.time < other.time <= c.time + FOLLOW_UP_WINDOW and other.bounces_up:
                return other
        return None

    def played_on(self, c: Contact) -> bool:
        """Did a player (not the floor) touch the ball next?"""
        follow = self.next_rising(c)
        return follow is not None and (c.y - follow.y) * self.m >= PLAYER_ABOVE_FLOOR

    def side(self, x: float) -> int:
        return 1 if x >= self.net else -1

    def rebound(self, c: Contact) -> tuple[float, bool]:
        """Metres the ball climbs after `c`, and whether it left the frame."""
        follow = self.next_rising(c)
        last = follow.index if follow else c.index + int(REBOUND_WINDOW * self.traj.fps)
        last = min(last, self.traj.n - 1)
        ys = self.traj.y[c.index + 1:last + 1]
        known = ~np.isnan(ys)
        if not known.any():
            return 0.0, False
        rise = (c.y - np.nanmin(ys)) * self.m
        final = ys[np.flatnonzero(known)[-1]]
        left_frame = final <= TOP_EDGE and not known[-1]
        return max(0.0, float(rise)), bool(left_frame)


def _serve_receive(ctx: _RallyContext) -> Optional[Contact]:
    if ctx.rally.serve_time is None:
        return None
    for c in ctx.contacts:
        if c.time > ctx.rally.serve_time + SERVE_RECEIVE_DELAY and c.bounces_up:
            return c
    return None


def _landing_and_saves(ctx: _RallyContext) -> tuple[Optional[Contact], list[Contact]]:
    cfg = ctx.config
    receive = _serve_receive(ctx)
    landing, saves = None, []
    for c in ctx.contacts:
        after = ctx.rally.play_end - c.time
        if ctx.is_hard_falling_bounce(c, cfg.save_min_speed) and c is not receive:
            if ctx.played_on(c) and after >= cfg.save_min_play_after:
                saves.append(c)
                continue
        if landing is None and ctx.is_hard_falling_bounce(c, cfg.attack_min_speed):
            if not ctx.played_on(c) and after <= cfg.rally_end_window:
                landing = c
    return landing, saves


def _big_kill(ctx: _RallyContext, landing: Optional[Contact]) -> Optional[Highlight]:
    cfg = ctx.config
    if landing is None:
        return None
    rise, left_frame = ctx.rebound(landing)
    if rise < cfg.big_kill_min_rise:
        return None
    speed = ctx.speed_in(landing)
    note = "+ (left the frame)" if left_frame else ""
    return Highlight(
        kind="big_kill",
        time=round(landing.time, 2),
        score=_ramp(rise, cfg.big_kill_min_rise, cfg.big_kill_strong_rise),
        rally_index=ctx.rally.index,
        description=f"Ball rebounded ~{rise:.1f} m{note} after an attack at ~{speed:.0f} m/s",
        details={"rebound_m": round(rise, 2), "left_frame": left_frame, "attack_speed_ms": round(speed, 1)},
    )


def _great_save(ctx: _RallyContext, c: Contact) -> Highlight:
    cfg = ctx.config
    speed = ctx.speed_in(c)
    return Highlight(
        kind="great_save",
        time=round(c.time, 2),
        score=_ramp(speed, cfg.save_min_speed, cfg.save_strong_speed),
        rally_index=ctx.rally.index,
        description=f"Dug up a ball driven in at ~{speed:.0f} m/s",
        details={"incoming_speed_ms": round(speed, 1)},
    )


def _shutdown_block(ctx: _RallyContext) -> Optional[Highlight]:
    cfg = ctx.config
    m = ctx.m
    best = None
    for c in ctx.contacts:
        if abs(c.x - ctx.net) * m > cfg.net_zone:
            continue
        if cfg.net_top_y is not None and c.y > cfg.net_top_y + TOP_EDGE:
            continue  # below the tape: into the net, not a block
        speed = ctx.speed_in(c)
        if speed < cfg.block_min_speed:
            continue
        vx_in, vx_out, vy_out = c.v_in[0] * m, c.v_out[0] * m, c.v_out[1] * m
        attacker = ctx.side(c.x - c.v_in[0] * 0.1)  # where the ball came from
        if -attacker * vx_in < cfg.block_min_toward_net:
            continue
        sent_back = vx_out * vx_in < 0 or (abs(vx_out) < 1.0 and vy_out > 0)
        if not sent_back:
            continue
        if ctx.rally.play_end - c.time > cfg.block_end_window:
            continue
        if ctx.side(_resting_x(ctx, c)) != attacker:
            continue
        score = _ramp(speed, cfg.block_min_speed, cfg.block_strong_speed)
        if best is None or score > best.score:
            best = Highlight(
                kind="shutdown_block",
                time=round(c.time, 2),
                score=score,
                rally_index=ctx.rally.index,
                description=f"Stuffed an attack coming in at ~{speed:.0f} m/s",
                details={"attack_speed_ms": round(speed, 1)},
            )
    return best


def _resting_x(ctx: _RallyContext, c: Contact) -> float:
    """Where the ball came down after `c`: its next bounce, else last sighting."""
    follow = ctx.next_rising(c)
    if follow is not None:
        return follow.x
    last = min(ctx.traj.n - 1, c.index + int(ctx.config.block_end_window * ctx.traj.fps))
    xs = ctx.traj.x[c.index:last + 1]
    known = np.flatnonzero(~np.isnan(xs))
    return float(xs[known[-1]]) if known.size else c.x


def _crowd_reaction(rally: Rally, audio: AudioSignals, config: AnalysisConfig) -> tuple[float, Optional[Highlight]]:
    db, peak = audio.excitement(rally.play_end - 1.0, rally.play_end + config.crowd_window)
    if db < config.crowd_min_db:
        return db, None
    return db, Highlight(
        kind="crowd_reaction",
        time=round(rally.play_end, 2),
        score=_ramp(db, config.crowd_min_db, config.crowd_strong_db),
        rally_index=rally.index,
        description=f"Crowd got ~{db:.0f} dB louder than usual",
        details={"excitement_db": round(db, 1), "peak_time": round(peak, 2)},
    )


def _long_rally(rally: Rally, config: AnalysisConfig) -> Optional[Highlight]:
    length = rally.rally_length
    if length < config.long_rally_s:
        return None
    return Highlight(
        kind="long_rally",
        time=round(rally.play_end, 2),
        score=_ramp(length, config.long_rally_s, config.long_rally_strong_s),
        rally_index=rally.index,
        description=f"{length:.0f}-second rally",
        details={"rally_seconds": round(length, 1)},
    )


def detect_highlights(
    rallies: list[Rally],
    traj: Trajectory,
    audio: AudioSignals,
    metres_per_fh: float,
    config: AnalysisConfig,
) -> list[Highlight]:
    highlights: list[Highlight] = []
    for rally in rallies:
        ctx = _RallyContext(rally, traj, metres_per_fh, config)
        landing, saves = _landing_and_saves(ctx)
        found = [h for h in (_big_kill(ctx, landing), _shutdown_block(ctx), _long_rally(rally, config)) if h]
        found += [_great_save(ctx, c) for c in saves]

        db, crowd = _crowd_reaction(rally, audio, config)
        if db > 0:
            boost = config.crowd_boost * min(1.0, db / config.crowd_strong_db)
            for h in found:
                h.score = min(1.0, h.score + boost)
        if crowd:
            found.append(crowd)

        for h in found:
            h.score = round(h.score, 3)
        highlights += sorted(found, key=lambda h: h.time)
    return highlights
