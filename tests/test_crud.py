def test_singer_crud_and_consent_defaults(client):
    r = client.post("/singers", json={"name": "Alex"})
    assert r.status_code == 201
    singer = r.json()
    assert singer["consent_training"] is False
    assert singer["consent_generation"] is False
    assert singer["training_status"] == "none"

    sid = singer["id"]
    assert client.get(f"/singers/{sid}").status_code == 200
    assert client.get("/singers").json()[0]["name"] == "Alex"

    r = client.patch(f"/singers/{sid}", json={"consent_generation": True, "scream_enabled": True})
    assert r.json()["consent_generation"] is True
    assert r.json()["scream_enabled"] is True

    assert client.delete(f"/singers/{sid}").status_code == 204
    assert client.get(f"/singers/{sid}").status_code == 404


def test_singer_name_uniqueness(client):
    assert client.post("/singers", json={"name": "Sam"}).status_code == 201
    assert client.post("/singers", json={"name": "Sam"}).status_code == 409


def test_many_singers_can_be_added(client):
    for i in range(12):
        assert client.post("/singers", json={"name": f"Singer {i}"}).status_code == 201
    assert len(client.get("/singers").json()) == 12


def test_project_and_song_crud(client):
    pid = client.post("/projects", json={"name": "Debut EP"}).json()["id"]
    r = client.post("/songs", json={"title": "Opener", "project_id": pid, "seed": 42})
    assert r.status_code == 201
    song = r.json()
    assert song["status"] == "draft"
    assert song["seed"] == 42

    r = client.patch(f"/songs/{song['id']}", json={"status": "planning", "bpm": 140})
    assert r.json()["status"] == "planning"
    assert r.json()["bpm"] == 140

    assert client.delete(f"/projects/{pid}").status_code == 204
    # song cascades with the project
    assert client.get(f"/songs/{song['id']}").status_code == 404
