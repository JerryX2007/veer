from app.analysis.audio import AudioSignals
from app.analysis.config import AnalysisConfig
from app.analysis.highlights import detect_highlights
from app.analysis.pipeline import calibrate
from app.analysis.rallies import segment_rallies
from app.analysis.reel import build_reel
from tests import synthetic
from tests.test_trajectory import scripted_trajectory

import numpy as np


def run(traj, config=None):
    config = config or AnalysisConfig()
    contacts, metres, calibrated = calibrate(traj, config)
    assert calibrated
    rallies, source = segment_rallies(traj, contacts, np.zeros(traj.n), [], traj.n / traj.fps, metres, config)
    assert source == "ball"
    return rallies, detect_highlights(rallies, traj, AudioSignals(), metres, config)


def test_rallies_run_from_serve_to_dead_ball():
    traj, _ = scripted_trajectory()
    rallies, _ = run(traj)
    script = synthetic.default_script()
    assert len(rallies) == len(script)
    start = 3.0
    for rally, scripted in zip(rallies, script):
        serve = start + scripted.serve_offset
        assert abs(rally.serve_time - serve) < 0.15
        assert abs(rally.start - (serve - 1.0)) < 0.15  # the toss is kept
        assert rally.end >= start + scripted.points[-1][0]
        start += scripted.points[-1][0] + 7.0


def test_ball_highlights_match_the_script():
    traj, _ = scripted_trajectory()
    _, highlights = run(traj)
    found = sorted((h.kind, h.rally_index) for h in highlights)
    assert found == [("big_kill", 0), ("great_save", 1), ("shutdown_block", 2)]
    for h in highlights:
        assert 0.5 <= h.score <= 1.0


def test_highlight_times_are_accurate():
    traj, _ = scripted_trajectory()
    _, highlights = run(traj)
    starts = {0: 3.0, 1: 3.0 + 8.2 + 7.0, 2: 3.0 + 8.2 + 7.0 + 9.7 + 7.0}
    expected = {"big_kill": (0, 5.35), "great_save": (1, 5.35), "shutdown_block": (2, 5.12)}
    for h in highlights:
        rally, offset = expected[h.kind]
        assert abs(h.time - (starts[rally] + offset)) <= 0.1


def test_ordinary_kill_is_not_a_big_kill():
    traj, _ = scripted_trajectory()
    _, highlights = run(traj)
    assert not any(h.rally_index == 3 for h in highlights)  # the plain rally


def test_raising_thresholds_suppresses_highlights():
    traj, _ = scripted_trajectory()
    config = AnalysisConfig(big_kill_min_rise=8.0, save_min_speed=40.0, block_min_speed=40.0)
    _, highlights = run(traj, config)
    assert highlights == []


def test_reel_uses_whole_rallies_of_highlights():
    traj, _ = scripted_trajectory()
    rallies, highlights = run(traj)
    reel = build_reel(rallies, highlights, min_score=0.5)
    assert [s.rally_indices for s in reel.segments] == [[0], [1], [2]]
    for seg in reel.segments:
        rally = rallies[seg.rally_indices[0]]
        assert (seg.start, seg.end) == (rally.start, rally.end)
        for h in seg.highlights:
            assert seg.start <= h.time <= seg.end
