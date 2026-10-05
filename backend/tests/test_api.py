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
