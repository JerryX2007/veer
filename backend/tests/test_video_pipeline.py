"""End to end: render a synthetic match, then analyse the actual video file."""

import shutil

import pytest

from app.analysis import analyze_video
from tests import synthetic

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def result_and_truth(tmp_path_factory):
    match = synthetic.make_match(tmp_path_factory.mktemp("video") / "match.mp4")
    progress = []
    result = analyze_video(str(match.path), progress=progress.append)
    assert progress[-1] == 1.0
    return result, match


def test_finds_every_rally_from_the_serve(result_and_truth):
    result, match = result_and_truth
    assert len(result.rallies) == len(match.rallies)
    for found, truth in zip(result.rallies, match.rallies):
        assert found.serve_time is not None
        assert abs(found.serve_time - truth.serve_time) < 0.2
        assert found.start <= truth.serve_time - 0.5
        assert found.end >= truth.play_end


def test_finds_the_scripted_highlights(result_and_truth):
    result, match = result_and_truth
    expected = {(kind, i) for i, r in enumerate(match.rallies) for kind, _ in r.highlights}
    found = {(h.kind, h.rally_index) for h in result.highlights}
    assert expected <= found
    # Only the big-kill rally also gets a crowd reaction on top.
    assert found - expected == {("crowd_reaction", 0)}
    for h in result.highlights:
        truth = dict(match.rallies[h.rally_index].highlights).get(h.kind)
        if truth is not None and h.kind != "crowd_reaction":
            assert abs(h.time - truth) < 0.15


def test_reel_skips_the_plain_rally(result_and_truth):
    result, _ = result_and_truth
    assert [s.rally_indices for s in result.reel.segments] == [[0], [1], [2], [4]]


def test_diagnostics(result_and_truth):
    result, match = result_and_truth
    d = result.diagnostics
    assert d["scale_calibrated"] and abs(d["metres_per_frame_height"] - 12) < 0.6
    assert d["rally_source"] == "ball"
    assert len(d["whistles"]) == len(match.whistles)
