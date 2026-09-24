"""Scoring detected rallies against rallies you tagged by hand.

The manual tagger doubles as a labelled dataset: tag a match's rallies,
run detection, and this tells you how many were found (recall), how many
detections were real (precision) and how far off the start/end times are.
Use it to tune `AnalysisConfig` on your own footage.
"""

from typing import Optional, Sequence

Span = tuple[float, float]


def overlap_ratio(a: Span, b: Span) -> float:
    """Intersection over union of two time ranges."""
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def evaluate_rallies(detected: Sequence[Span], tagged: Sequence[Span], min_overlap: float = 0.5) -> dict:
    """Greedily pair detections with tags (best overlap first), then score."""
    pairs = sorted(
        ((overlap_ratio(d, t), di, ti) for di, d in enumerate(detected) for ti, t in enumerate(tagged)),
        reverse=True,
    )
    used_d, used_t, matches = set(), set(), []
    for ratio, di, ti in pairs:
        if ratio < min_overlap:
            break
        if di in used_d or ti in used_t:
            continue
        used_d.add(di)
        used_t.add(ti)
        matches.append((detected[di], tagged[ti]))

    def mean(values: list[float]) -> Optional[float]:
        return round(sum(values) / len(values), 2) if values else None

    return {
        "tagged_rallies": len(tagged),
        "detected_rallies": len(detected),
        "matched": len(matches),
        "precision": round(len(matches) / len(detected), 3) if detected else 0.0,
        "recall": round(len(matches) / len(tagged), 3) if tagged else 0.0,
        "mean_start_error": mean([d[0] - t[0] for d, t in matches]),
        "mean_end_error": mean([d[1] - t[1] for d, t in matches]),
    }
