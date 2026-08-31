"""Stage 1: section editing, reordering, and the lyrics-block editor."""

from __future__ import annotations


def test_section_patch_and_reorder(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    ids = [
        client.post(
            f"/songs/{song_id}/sections", json={"section_type": "verse", "order_index": i}
        ).json()["id"]
        for i in range(3)
    ]

    client.patch(
        f"/songs/{song_id}/sections/{ids[0]}",
        json={"section_type": "intro", "start_time": 0, "end_time": 8, "name": "Intro"},
    )
    got = client.get(f"/songs/{song_id}/sections").json()
    assert got[0]["section_type"] == "intro"
    assert got[0]["end_time"] == 8

    reordered = client.put(
        f"/songs/{song_id}/sections/reorder", json=[ids[2], ids[0], ids[1]]
    ).json()
    assert [x["id"] for x in reordered] == [ids[2], ids[0], ids[1]]
    assert [x["order_index"] for x in reordered] == [0, 1, 2]


def test_reorder_rejects_wrong_id_set(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    a = client.post(f"/songs/{song_id}/sections", json={"section_type": "verse"}).json()["id"]
    assert client.put(f"/songs/{song_id}/sections/reorder", json=[a, "extra"]).status_code == 422


def test_lyrics_replace_rebuilds_lines(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    client.put(f"/songs/{song_id}/lines", json={"text": "a\nb\nc"})
    lines = client.get(f"/songs/{song_id}/lines").json()
    assert [ln["text"] for ln in lines] == ["a", "b", "c"]
    assert [ln["order_index"] for ln in lines] == [0, 1, 2]

    client.put(f"/songs/{song_id}/lines", json={"text": "just one"})
    lines = client.get(f"/songs/{song_id}/lines").json()
    assert [ln["text"] for ln in lines] == ["just one"]


def test_line_patch_moves_between_sections(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    v = client.post(f"/songs/{song_id}/sections", json={"section_type": "verse"}).json()["id"]
    c = client.post(f"/songs/{song_id}/sections", json={"section_type": "chorus"}).json()["id"]
    line = client.post(f"/songs/{song_id}/lines", json={"text": "x", "section_id": v}).json()["id"]
    r = client.patch(f"/songs/{song_id}/lines/{line}", json={"section_id": c, "text": "y"})
    assert r.json()["section_id"] == c
    assert r.json()["text"] == "y"
