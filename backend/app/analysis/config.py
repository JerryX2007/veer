"""Every tunable knob of the auto-highlight pipeline, in one place.

Physical thresholds are in metres and metres/second. The pipeline converts
pixels to metres by measuring gravity on the ball's free-flight arcs (a ball
in the air always falls at 9.81 m/s^2), so the same thresholds work whether
the camera is zoomed in on one half or showing the whole court. When too few
clean arcs are found it falls back to `default_metres_per_frame_height`.

The defaults assume a roughly side-on camera (the net runs vertically through
the frame, near `net_x`). They are starting points: tune them against rallies
you've tagged by hand (see `app.analysis.evaluate`).
"""

from dataclasses import asdict, dataclass, fields
from typing import Any, Optional


@dataclass
class AnalysisConfig:
    # --- Decoding -----------------------------------------------------------
    analysis_fps: float = 30.0  # capped at the source frame rate
    analysis_width: int = 640  # frames are downscaled to this width

    # --- Ball candidates (sizes as a fraction of frame height) -------------
    diff_threshold: int = 18  # grey-level change that counts as motion
    ball_min_radius: float = 0.004
    ball_max_radius: float = 0.03
    ball_max_aspect: float = 3.0  # motion blur stretches the ball
    ball_min_fill: float = 0.3  # blob area / enclosing-circle area
    max_candidates_per_frame: int = 15  # more than this = camera shake, skip frame

    # --- Tracking -----------------------------------------------------------
    track_gate: float = 0.06  # association radius, frame heights (+ speed term)
    track_max_missed: int = 4  # frames a track may coast without a detection
    track_min_length: int = 8  # detections needed to keep a tracklet
    track_min_speed: float = 3.0  # m/s, median; drops heads/hands bobbing about
    max_interp_gap: int = 6  # frames of occlusion to bridge by interpolation

    # --- Scale calibration --------------------------------------------------
    default_metres_per_frame_height: float = 13.5  # whole court, side-on
    gravity_min_flights: int = 3

    # --- Contacts (anything that abruptly changes the ball's velocity) -----
    contact_window: float = 0.2  # s of trajectory fitted either side
    contact_min_dv: float = 4.0  # m/s change beyond what gravity explains

    # --- Rally segmentation -------------------------------------------------
    active_min_speed: float = 2.0  # m/s; slower is a held / rolling ball
    rally_max_gap: float = 2.5  # s of no ball activity that ends a rally
    rally_min_duration: float = 3.0
    serve_min_speed: float = 5.0  # m/s when first crossing the net
    serve_lookback: float = 2.5  # s before the net crossing to find the hit
    serve_preroll: float = 1.0  # s kept before the serve (the toss)
    rally_postroll: float = 1.5  # s kept after the ball goes dead
    whistle_end_window: float = 3.0  # whistle this soon after play extends the end
    # Below this share of frames with a tracked ball, fall back to segmenting
    # rallies on overall motion (and only audio/duration highlights work).
    motion_fallback_coverage: float = 0.02

    # --- Court geometry (fractions of the frame) ----------------------------
    net_x: float = 0.5  # where the net crosses the frame, 0 = left, 1 = right
    net_top_y: Optional[float] = None  # net tape height if known, 0 = top
    net_zone: float = 1.5  # m either side of the net that counts as "at the net"

    # --- Highlight: big kill (ball rebounds high off the floor) -------------
    attack_min_speed: float = 10.0  # m/s into the floor for it to be an attack
    attack_min_steepness: float = 0.35  # downward share of that speed
    big_kill_min_rise: float = 3.0  # m the ball climbs after the bounce
    big_kill_strong_rise: float = 6.0
    rally_end_window: float = 4.0  # s: a landing this close to the end ended it

    # --- Highlight: great save (hard-driven ball dug back up) ---------------
    save_min_speed: float = 10.0
    save_strong_speed: float = 22.0
    save_min_play_after: float = 1.5  # s the rally must continue afterwards

    # --- Highlight: shutdown block ------------------------------------------
    block_min_speed: float = 9.0  # m/s of the attack into the block
    block_min_toward_net: float = 5.0  # m/s of that aimed at the net
    block_strong_speed: float = 22.0
    block_end_window: float = 3.0  # s: the rally must die this soon after

    # --- Highlight: crowd reaction (audio) ----------------------------------
    crowd_min_db: float = 6.0  # above the match's typical loudness
    crowd_strong_db: float = 15.0
    crowd_window: float = 4.0  # s after play ends to listen for a roar
    crowd_boost: float = 0.15  # max score added to other highlights

    # --- Highlight: long rally ----------------------------------------------
    long_rally_s: float = 18.0
    long_rally_strong_s: float = 35.0

    # --- Reel ---------------------------------------------------------------
    reel_min_score: float = 0.5  # every detected highlight scores >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_overrides(cls, overrides: Optional[dict[str, Any]] = None) -> "AnalysisConfig":
        """Build a config from defaults plus `overrides`, rejecting unknown keys."""
        overrides = overrides or {}
        defaults = cls()
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(overrides) - known)
        if unknown:
            raise ValueError(f"Unknown analysis setting(s): {', '.join(unknown)}")

        values = {}
        for name, value in overrides.items():
            default = getattr(defaults, name)
            if value is None and default is None:
                values[name] = None
                continue
            kind = int if isinstance(default, int) else float
            try:
                values[name] = kind(value)
            except (TypeError, ValueError):
                raise ValueError(f"Analysis setting {name!r} must be a number") from None
        return cls(**values)
