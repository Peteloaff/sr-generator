"""Stage 1 exit criterion: build a project, export it, re-import it, identical."""

from __future__ import annotations


def _build_project(client) -> str:
    pid = client.post("/projects", json={"name": "Debut"}).json()["id"]
    song_id = client.post("/songs", json={"title": "Track 1", "project_id": pid, "seed": 5}).json()[
        "id"
    ]
    singers = {
        n: client.post("/singers", json={"name": n}).json()["id"] for n in ("Brian", "Pete", "Brad")
    }
    for i, stype in enumerate(("verse", "chorus", "breakdown")):
        sec = client.post(
            f"/songs/{song_id}/sections",
            json={"section_type": stype, "order_index": i, "name": stype.title()},
        ).json()
        client.post(
            f"/sections/{sec['id']}/roles",
            json={
                "role_type": "lead" if stype != "breakdown" else "scream",
                "assignments": [{"singer_id": singers["Brian" if stype == "chorus" else "Pete"]}],
            },
        )
        if stype == "chorus":
            client.post(
                f"/sections/{sec['id']}/roles",
                json={
                    "role_type": "background",
                    "ensemble_size": 10,
                    "width": 85,
                    "assignments": [
                        {"singer_id": singers["Brian"], "weight_percent": 70, "gain_db": -6},
                        {"singer_id": singers["Pete"], "weight_percent": 20, "pan": -30},
                        {"singer_id": singers["Brad"], "weight_percent": 10, "pan": 30},
                    ],
                },
            )
    client.put(
        f"/songs/{song_id}/lines",
        json={"text": "line one\nline two\nline three"},
    )
    return pid


def test_export_import_roundtrip_is_identical(client):
    pid = _build_project(client)
    export_a = client.get(f"/projects/{pid}/export").json()

    imported = client.post("/projects/import", json=export_a)
    assert imported.status_code == 201
    export_b = client.get(f"/projects/{imported.json()['id']}/export").json()

    assert export_a == export_b


def test_import_into_another_band_creates_placeholder_singers(client):
    pid = _build_project(client)
    export = client.get(f"/projects/{pid}/export").json()

    other = client.post("/bands", json={"name": "Cover Band"}).json()["id"]
    imported = client.post(
        "/projects/import", json=export, headers={"X-Band-Id": other}
    ).json()

    assert client.get(f"/projects/{imported['id']}").json()["band_id"] == other
    # singers were recreated in the target band, blocked from generation by default
    new_singers = client.get("/singers", params={"band_id": other}).json()
    assert {s["name"] for s in new_singers} == {"Brian", "Pete", "Brad"}
    assert all(s["consent_generation"] is False for s in new_singers)


def test_import_rejects_bad_version(client):
    r = client.post("/projects/import", json={"sr_export_version": 999, "project": {"name": "x"}})
    assert r.status_code == 422
