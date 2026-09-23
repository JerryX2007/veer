import shutil

import pytest
from fastapi.testclient import TestClient

from app.analysis.media import probe
from tests import synthetic

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def client():
    from app.main import app  # after the working directory has been isolated

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def match_id(client, tmp_path_factory):
    video = synthetic.make_match(tmp_path_factory.mktemp("api") / "api_match.mp4").path
    with open(video, "rb") as f:
        res = client.post("/matches/", data={"title": "Synthetic"}, files={"file": ("api_match.mp4", f, "video/mp4")})
    assert res.status_code == 200
    return res.json()["id"]


@pytest.fixture(scope="module")
def analysis(client, match_id):
    # TestClient runs background tasks before returning, so the run is finished here.
    res = client.post(f"/matches/{match_id}/analysis/", json={"settings": {"net_x": 0.5}})
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "pending"
    res = client.get(f"/matches/{match_id}/analysis/")
    assert res.status_code == 200
    return res.json()


def test_analysis_results(analysis):
    assert analysis["status"] == "done", analysis["error"]
    assert analysis["progress"] == 1.0
    assert len(analysis["rallies"]) == 5
    kinds = sorted(h["kind"] for r in analysis["rallies"] for h in r["highlights"])
    assert kinds == ["big_kill", "crowd_reaction", "crowd_reaction", "great_save", "shutdown_block"]
    first = analysis["rallies"][0]["highlights"][0]
    assert first["label"] == "Big kill" and first["description"]


def test_reel_is_timestamps_of_whole_rallies(client, match_id, analysis):
    reel = client.get(f"/matches/{match_id}/analysis/reel").json()
    rallies = {r["index"]: r for r in analysis["rallies"]}
    assert [s["rally_indices"] for s in reel["segments"]] == [[0], [1], [2], [4]]
    for seg in reel["segments"]:
        rally = rallies[seg["rally_indices"][0]]
        assert (seg["start"], seg["end"]) == (rally["start_time"], rally["end_time"])
    assert reel["text"].startswith("Highlight reel: 4 clip(s)")
    assert analysis["reel"] == reel


def test_rejecting_a_highlight_updates_the_reel(client, match_id, analysis):
    block = next(h for r in analysis["rallies"] for h in r["highlights"] if h["kind"] == "shutdown_block")
    assert client.delete(f"/matches/{match_id}/analysis/highlights/{block['id']}").status_code == 204
    reel = client.get(f"/matches/{match_id}/analysis/reel").json()
    assert [s["rally_indices"] for s in reel["segments"]] == [[0], [1], [4]]
    assert client.delete(f"/matches/{match_id}/analysis/highlights/{block['id']}").status_code == 404


def test_evaluation_against_hand_tagged_rallies(client, match_id, analysis):
    assert client.get(f"/matches/{match_id}/analysis/evaluation").status_code == 400
    for r in analysis["rallies"][:3]:
        client.post(f"/matches/{match_id}/rallies/", json={
            "start_time": r["serve_time"] - 0.5, "end_time": r["end_time"] - 1.0, "outcome": "kill",
        })
    ev = client.get(f"/matches/{match_id}/analysis/evaluation").json()
    assert ev["matched"] == 3 and ev["recall"] == 1.0 and ev["precision"] == 0.6
    assert ev["mean_end_error"] == 1.0


def test_render_reel(client, match_id, analysis):
    res = client.post(f"/matches/{match_id}/analysis/reel/render")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["segment_count"] == 3  # the block was rejected above
    assert abs(probe(body["reel_path"]).duration - body["duration"]) < 0.5


def test_errors(client, match_id):
    assert client.post("/matches/999/analysis/").status_code == 404
    assert client.get("/matches/999/analysis/").status_code == 404
    res = client.post(f"/matches/{match_id}/analysis/", json={"settings": {"bogus": 1}})
    assert res.status_code == 422 and "bogus" in res.json()["detail"]
