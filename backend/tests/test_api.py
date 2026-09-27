<<<<<<< Updated upstream
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
=======
import pytest


def upload(client, path, title="Scrimmage", played_on="2026-09-20"):
    with open(path, "rb") as f:
        r = client.post("/matches", files={"file": (path.name, f, "video/mp4")},
                        data={"title": title, "played_on": played_on})
    assert r.status_code == 201, r.text
    return r.json()


def tag(client, match_id, **body):
    r = client.post(f"/matches/{match_id}/rallies", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_rejects_non_video(client, tmp_path):
    bad = tmp_path / "notes.mp4"
    bad.write_text("not a video")
    with open(bad, "rb") as f:
        r = client.post("/matches", files={"file": ("notes.mp4", f)}, data={"title": "x"})
    assert r.status_code == 422


def test_full_highlight_flow(client, footage):
    match = upload(client, footage["hd"])
    assert match["duration"] == pytest.approx(20, abs=0.1)
    assert client.get(match["video_url"]).status_code == 200

    kill = tag(client, match["id"], start=2, end=5, outcome="kill", skills=["attack"], player="me")
    ace = tag(client, match["id"], start=8, end=9.5, outcome="ace", skills=["serve"], player="me")
    tag(client, match["id"], start=12, end=16, outcome="error", skills=["pass"])
    tag(client, match["id"], start=17, end=19.8, outcome="kill", player="7")

    # Clips are cut (sync jobs in tests) with padding, clamped to the video's end.
    assert kill["clip"]["status"] == "ready"
    assert kill["clip"]["duration"] == pytest.approx(3 + 1.0 + 1.5, abs=0.15)
    assert client.get(kill["clip"]["url"]).status_code == 200
    assert client.get(kill["clip"]["thumbnail_url"]).status_code == 200
    assert kill["is_highlight"] and ace["is_highlight"]

    # Purple path: only serve/attack clips wait for pose estimation.
    queue = client.get("/pipeline/pose-queue").json()
    assert {c["id"] for c in queue} == {kill["clip"]["id"], ace["clip"]["id"]}

    # Teal path: "all my kills and aces" → one reel.
    r = client.post("/reels", json={"title": "My highlights", "player": "me", "highlights_only": True})
    assert r.status_code == 202, r.text
    reel = r.json()
    assert reel["status"] == "ready"
    assert reel["clip_ids"] == [kill["clip"]["id"], ace["clip"]["id"]]
    expected = kill["clip"]["duration"] + ace["clip"]["duration"]
    assert reel["duration"] == pytest.approx(expected, abs=0.25)
    dl = client.get(f"/reels/{reel['id']}/download")
    assert dl.status_code == 200 and dl.headers["content-type"] == "video/mp4"

    # Filter by outcome across players.
    r = client.post("/reels", json={"title": "All kills", "outcomes": ["kill"]})
    assert len(r.json()["clip_ids"]) == 2


def test_edit_rally_recuts_and_updates_pose_queue(client, footage):
    match = upload(client, footage["hd"])
    rally = tag(client, match["id"], start=2, end=4, outcome="dig", skills=["dig"])
    assert rally["clip"]["pose_status"] == "not_applicable"

    r = client.patch(f"/rallies/{rally['id']}", json={"skills": ["attack"]})
    assert r.json()["clip"]["pose_status"] == "queued"

    r = client.patch(f"/rallies/{rally['id']}", json={"end": 8})
    clip = r.json()["clip"]
    assert clip["status"] == "ready"
    assert clip["duration"] == pytest.approx(6 + 2.5, abs=0.15)


def test_rally_validation(client, footage):
    match = upload(client, footage["hd"])
    assert client.post(f"/matches/{match['id']}/rallies",
                       json={"start": 5, "end": 3, "outcome": "kill"}).status_code == 422
    assert client.post(f"/matches/{match['id']}/rallies",
                       json={"start": 18, "end": 40, "outcome": "kill"}).status_code == 422
    assert client.post(f"/matches/{match['id']}/rallies",
                       json={"start": 1, "end": 2, "outcome": "spike"}).status_code == 422


def test_reel_with_no_matches_is_rejected(client, footage):
    upload(client, footage["hd"])
    assert client.post("/reels", json={"outcomes": ["block"]}).status_code == 422


def test_mixed_matches_reel_and_delete(client, footage):
    a = upload(client, footage["hd"], played_on="2026-09-01")
    b = upload(client, footage["sd_silent"], played_on="2026-09-08")
    ra = tag(client, a["id"], start=1, end=3, outcome="block")
    rb = tag(client, b["id"], start=1, end=3, outcome="block")
    reel = client.post("/reels", json={"outcomes": ["block"]}).json()
    assert reel["status"] == "ready" and reel["clip_ids"] == [ra["clip"]["id"], rb["clip"]["id"]]

    assert client.delete(f"/matches/{b['id']}").status_code == 204
    assert client.get(rb["clip"]["url"]).status_code == 404
    assert len(client.get("/matches").json()) == 1
>>>>>>> Stashed changes
