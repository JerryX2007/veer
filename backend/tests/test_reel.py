import pytest

from app.analysis.config import AnalysisConfig
from app.analysis.highlights import Highlight
from app.analysis.rallies import Rally
from app.analysis.reel import build_reel, format_time, reel_to_text


def rally(i, start, end):
    return Rally(index=i, start=start, end=end, play_start=start + 1, play_end=end - 1)


def hl(i, t, score=0.8, kind="big_kill"):
    return Highlight(kind=kind, time=t, score=score, rally_index=i, description="")


def test_reel_positions_accumulate():
    rallies = [rally(0, 10, 20), rally(1, 30, 45), rally(2, 60, 70)]
    reel = build_reel(rallies, [hl(0, 18), hl(2, 65)], min_score=0.5)
    assert [(s.start, s.end, s.reel_start) for s in reel.segments] == [(10, 20, 0), (60, 70, 10)]
    assert reel.duration == 20
    assert reel.segments[1].reel_time(65) == 15


def test_low_scores_are_left_out():
    reel = build_reel([rally(0, 10, 20)], [hl(0, 15, score=0.4)], min_score=0.5)
    assert reel.segments == []
    assert reel_to_text(reel) == "No highlights found."


def test_overlapping_rallies_merge():
    reel = build_reel([rally(0, 10, 20), rally(1, 19, 30)], [hl(0, 15), hl(1, 25)], min_score=0.5)
    assert len(reel.segments) == 1
    seg = reel.segments[0]
    assert (seg.start, seg.end, seg.rally_indices) == (10, 30, [0, 1])


def test_to_dict_has_reel_times():
    reel = build_reel([rally(0, 10, 20), rally(1, 30, 40)], [hl(0, 12), hl(1, 35)], min_score=0.5)
    data = reel.to_dict()
    assert data["segments"][1]["highlights"][0]["reel_time"] == 15
    assert data["segments"][1]["reel_end"] == 20


@pytest.mark.parametrize("seconds, text", [(0, "0:00.0"), (65.34, "1:05.3"), (59.96, "1:00.0"), (3725.0, "1:02:05.0")])
def test_format_time(seconds, text):
    assert format_time(seconds) == text


def test_config_overrides():
    config = AnalysisConfig.from_overrides({"net_x": "0.4", "track_min_length": 5, "net_top_y": None})
    assert config.net_x == 0.4 and config.track_min_length == 5
    with pytest.raises(ValueError, match="Unknown"):
        AnalysisConfig.from_overrides({"nope": 1})
    with pytest.raises(ValueError, match="number"):
        AnalysisConfig.from_overrides({"net_x": "left"})
