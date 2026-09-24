"""Turning highlights into a highlight reel made of timestamps.

The reel doesn't cut anything: it's an ordered list of source-video time
ranges, one per rally that contains a highlight, running from the serve to
the end of the rally. Each highlight's moment is also given as a position in
the reel. A player can play the reel by seeking through the ranges, or
`services.video.render_segments` can turn it into one mp4.
"""

from dataclasses import dataclass, field
from typing import Iterable

from .highlights import Highlight
from .rallies import Rally


@dataclass
class ReelSegment:
    start: float  # seconds into the source video
    end: float
    reel_start: float  # where this segment begins in the reel
    rally_indices: list[int] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def reel_time(self, source_time: float) -> float:
        return self.reel_start + (source_time - self.start)


@dataclass
class Reel:
    segments: list[ReelSegment] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    def to_dict(self) -> dict:
        return {
            "duration": round(self.duration, 2),
            "segments": [
                {
                    "start": round(s.start, 2),
                    "end": round(s.end, 2),
                    "reel_start": round(s.reel_start, 2),
                    "reel_end": round(s.reel_start + s.duration, 2),
                    "rally_indices": s.rally_indices,
                    "highlights": [
                        {
                            "kind": h.kind,
                            "label": h.label,
                            "time": h.time,
                            "reel_time": round(s.reel_time(h.time), 2),
                            "score": h.score,
                            "description": h.description,
                        }
                        for h in s.highlights
                    ],
                }
                for s in self.segments
            ],
        }


def build_reel(rallies: Iterable[Rally], highlights: Iterable[Highlight], min_score: float) -> Reel:
    """One segment per highlighted rally (serve to end), in match order.

    Rallies whose clips overlap are merged into a single segment.
    """
    by_rally: dict[int, list[Highlight]] = {}
    for h in highlights:
        if h.score >= min_score:
            by_rally.setdefault(h.rally_index, []).append(h)

    segments: list[ReelSegment] = []
    for rally in sorted(rallies, key=lambda r: r.start):
        found = by_rally.get(rally.index)
        if not found:
            continue
        found = sorted(found, key=lambda h: h.time)
        if segments and rally.start <= segments[-1].end:
            last = segments[-1]
            last.end = max(last.end, rally.end)
            last.rally_indices.append(rally.index)
            last.highlights += found
            continue
        segments.append(ReelSegment(rally.start, rally.end, 0.0, [rally.index], found))

    position = 0.0
    for s in segments:
        s.reel_start = position
        position += s.duration
    return Reel(segments)


def format_time(seconds: float) -> str:
    """1:05.3 or 1:02:05.3"""
    seconds = round(max(0.0, seconds), 1)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours >= 1:
        return f"{int(hours)}:{int(minutes):02d}:{secs:04.1f}"
    return f"{int(minutes)}:{secs:04.1f}"


def reel_to_text(reel: Reel) -> str:
    """A plain-text list of timestamps, e.g. to paste into a video description."""
    if not reel.segments:
        return "No highlights found."
    lines = [f"Highlight reel: {len(reel.segments)} clip(s), {format_time(reel.duration)} total"]
    for n, s in enumerate(reel.segments, 1):
        lines.append(
            f"{n}. reel {format_time(s.reel_start)}  |  source {format_time(s.start)} - {format_time(s.end)}"
        )
        for h in s.highlights:
            lines.append(
                f"     {h.label} at {format_time(h.time)} (reel {format_time(s.reel_time(h.time))}, "
                f"score {h.score:.2f}): {h.description}"
            )
    return "\n".join(lines)
