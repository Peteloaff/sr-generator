"""Section + lyric-line structure and the line-overrides-section resolution rule."""

from __future__ import annotations

from sr.common.resolver import resolve_line_roles
from sr.db import session_scope
from sr.models.song import LyricLine, Song, SongSection
from sr.models.vocal import VocalAssignment, VocalRole


def test_lines_attach_to_song_and_section(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    sec_id = client.post(
        f"/songs/{song_id}/sections", json={"section_type": "chorus", "order_index": 0}
    ).json()["id"]

    l1 = client.post(
        f"/songs/{song_id}/lines", json={"text": "line one", "section_id": sec_id, "order_index": 0}
    )
    assert l1.status_code == 201
    assert l1.json()["section_id"] == sec_id

    bad = client.post(f"/songs/{song_id}/lines", json={"text": "x", "section_id": "nope"})
    assert bad.status_code == 404

    assert len(client.get(f"/songs/{song_id}/lines").json()) == 1


def test_resolver_line_overrides_section(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    sec_id = client.post(
        f"/songs/{song_id}/sections", json={"section_type": "chorus"}
    ).json()["id"]
    brian = client.post("/singers", json={"name": "Brian"}).json()["id"]
    pete = client.post("/singers", json={"name": "Pete"}).json()["id"]

    line_inherit = client.post(
        f"/songs/{song_id}/lines", json={"text": "inherits", "section_id": sec_id}
    ).json()["id"]
    line_override = client.post(
        f"/songs/{song_id}/lines", json={"text": "overrides", "section_id": sec_id}
    ).json()["id"]

    with session_scope() as db:
        section = db.get(SongSection, sec_id)
        sec_role = VocalRole(section_id=section.id, role_type="lead", ensemble_size=1)
        sec_role.assignments.append(VocalAssignment(singer_id=brian, weight_percent=100))
        db.add(sec_role)

        line = db.get(LyricLine, line_override)
        line_role = VocalRole(lyric_line_id=line.id, role_type="lead", ensemble_size=1)
        line_role.assignments.append(VocalAssignment(singer_id=pete, weight_percent=100))
        db.add(line_role)

    inherit = client.get(f"/songs/{song_id}/lines/{line_inherit}/resolved-roles").json()
    assert inherit["source"] == "section"
    assert inherit["roles"][0]["assignments"][0]["singer_id"] == brian

    override = client.get(f"/songs/{song_id}/lines/{line_override}/resolved-roles").json()
    assert override["source"] == "line"
    assert override["roles"][0]["assignments"][0]["singer_id"] == pete


def test_resolver_none_when_no_roles(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    line_id = client.post(f"/songs/{song_id}/lines", json={"text": "bare"}).json()["id"]
    with session_scope() as db:
        assert resolve_line_roles(db.get(LyricLine, line_id)).source == "none"
    # keep Song import referenced for lint
    assert Song.__tablename__ == "songs"
