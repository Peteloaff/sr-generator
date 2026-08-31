"""Stage gate: check a stage's exit criteria and print PASS/FAIL.

Usage:
  python scripts/stage_gate.py            # the latest implemented stage
  python scripts/stage_gate.py 0          # a specific stage

Exits non-zero if any criterion fails - do not proceed to the next stage.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _isolated_env() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sr-gate-"))
    os.environ["SR_DATABASE_URL"] = f"sqlite:///{(tmp / 'gate.db').as_posix()}"
    os.environ["SR_STORAGE_ROOT"] = tmp.as_posix()
    os.environ["SR_QUEUE_BACKEND"] = "inline"
    os.environ["SR_LOG_LEVEL"] = "WARNING"


def _client():
    from fastapi.testclient import TestClient

    from sr.api.main import create_app
    from sr.db import engine
    from sr.models import Base

    Base.metadata.create_all(engine)
    return TestClient(create_app())


def _wav_bytes(seconds: float = 1.0, rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


Row = tuple[str, bool, str]


def stage0(client) -> list[Row]:
    rows: list[Row] = []
    h = client.get("/health").json()
    rows.append(("Stack boots locally (API + DB + providers)", h["status"] == "ok", h["status"]))

    try:
        s = client.post("/singers", json={"name": "GateSinger"}).json()
        client.patch(f"/singers/{s['id']}", json={"consent_generation": True})
        p = client.post("/projects", json={"name": "GateProject"}).json()
        song = client.post("/songs", json={"title": "GateSong", "project_id": p["id"]}).json()
        ok = all(
            [
                client.get(f"/singers/{s['id']}").json()["consent_generation"] is True,
                client.get(f"/songs/{song['id']}").status_code == 200,
                client.delete(f"/singers/{s['id']}").status_code == 204,
                client.delete(f"/projects/{p['id']}").status_code == 204,
            ]
        )
        rows.append(("CRUD for singers / projects / songs", ok, "create/read/update/delete"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("CRUD for singers / projects / songs", False, repr(exc)))

    try:
        job = client.post(
            "/jobs",
            json={"job_type": "mock_generation", "seed": 7, "parameters": {"prompt": "g"}},
        ).json()
        done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 20}).json()
        ok = (
            done["status"] == "succeeded"
            and len(done["outputs"]) == 1
            and done["outputs"][0]["generation_job_id"] == done["id"]
        )
        rows.append(("Mock generation job queued -> completed (lineage)", bool(ok), done["status"]))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Mock generation job queued -> completed (lineage)", False, repr(exc)))
    return rows


def stage1(client) -> list[Row]:
    rows: list[Row] = []

    # 1. upload a song's audio
    try:
        song_id = client.post("/songs", json={"title": "Gate Demo"}).json()["id"]
        r = client.post(
            f"/songs/{song_id}/audio",
            files={"file": ("g.wav", _wav_bytes(2.0), "audio/wav")},
        ).json()
        wf = client.get(f"/songs/{song_id}/assets/{r['id']}/waveform").json()
        ok = r["asset_type"] == "upload" and r["duration"] == 2.0 and wf["buckets"] > 100
        rows.append(("Upload existing audio + waveform", ok, f"{r.get('duration')}s"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Upload existing audio + waveform", False, repr(exc)))
        song_id = None

    # 2. mark Verse/Chorus/Breakdown + assign a singer/role to every section
    try:
        singers = {
            n: client.post("/singers", json={"name": n}).json()["id"]
            for n in ("Brian", "Pete", "Brad")
        }
        assigned = 0
        for stype in ("verse", "chorus", "breakdown"):
            sec = client.post(
                f"/songs/{song_id}/sections", json={"section_type": stype}
            ).json()
            role = client.post(
                f"/sections/{sec['id']}/roles",
                json={
                    "role_type": "lead",
                    "assignments": [{"singer_id": singers["Brian"], "weight_percent": 100}],
                },
            )
            if role.status_code == 201:
                assigned += 1
        rows.append(("Mark Verse/Chorus/Breakdown + assign roles", assigned == 3, f"{assigned}/3"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Mark Verse/Chorus/Breakdown + assign roles", False, repr(exc)))

    # 3. weighted background normalizes to the canonical allocation
    try:
        sec = client.post(f"/songs/{song_id}/sections", json={"section_type": "chorus"}).json()
        role = client.post(
            f"/sections/{sec['id']}/roles",
            json={
                "role_type": "background",
                "ensemble_size": 10,
                "assignments": [
                    {"singer_id": singers["Brian"], "weight_percent": 70},
                    {"singer_id": singers["Pete"], "weight_percent": 20},
                    {"singer_id": singers["Brad"], "weight_percent": 10},
                ],
            },
        ).json()
        takes = {x["singer_id"]: x["ensemble_takes"] for x in
                 client.get(f"/roles/{role['id']}/normalized").json()}
        ok = takes == {singers["Brian"]: 7, singers["Pete"]: 2, singers["Brad"]: 1}
        rows.append(("Weighted background 70/20/10 @ 10 -> 7/2/1", ok, str(sorted(takes.values()))))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Weighted background 70/20/10 @ 10 -> 7/2/1", False, repr(exc)))

    # 4. save and reload exactly (export -> import -> identical)
    try:
        pid = client.post("/projects", json={"name": "Gate Project"}).json()["id"]
        client.patch(f"/songs/{song_id}", json={"project_id": pid})
        client.put(f"/songs/{song_id}/lines", json={"text": "one\ntwo\nthree"})
        export_a = client.get(f"/projects/{pid}/export").json()
        imported = client.post("/projects/import", json=export_a).json()
        export_b = client.get(f"/projects/{imported['id']}/export").json()
        rows.append(("Project export -> import -> identical", export_a == export_b, "deep-equal"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Project export -> import -> identical", False, repr(exc)))

    # 5. band scoping: a second band is isolated
    try:
        b2 = client.post("/bands", json={"name": "Second"}).json()["id"]
        s2 = client.post("/singers", json={"name": "Brian"}, headers={"X-Band-Id": b2})
        listed = client.get("/singers", params={"band_id": b2}).json()
        ok = s2.status_code == 201 and len(listed) == 1
        rows.append(("Band scoping isolates a second band", ok, "same singer name allowed"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Band scoping isolates a second band", False, repr(exc)))

    return rows


def stage2(client) -> list[Row]:
    import hashlib

    rows: list[Row] = []
    singers = {
        n: client.post("/singers", json={"name": n}).json()["id"]
        for n in ("Brian", "Pete", "Brad")
    }
    song = client.post("/songs", json={"title": "Gate Render", "seed": 99}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "chorus", "start_time": 0, "end_time": 3},
    ).json()["id"]
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": singers["Brian"]}]},
    )
    client.post(
        f"/sections/{section}/roles",
        json={
            "role_type": "gang", "ensemble_size": 10, "width": 85,
            "humanize_timing_ms": 18, "humanize_pitch_cents": 6,
            "assignments": [
                {"singer_id": singers["Brian"], "weight_percent": 70},
                {"singer_id": singers["Pete"], "weight_percent": 20},
                {"singer_id": singers["Brad"], "weight_percent": 10},
            ],
        },
    )

    def render_hash(seed):
        job = client.post(
            f"/songs/{song}/sections/{section}/render", json={"seed": seed}
        ).json()
        job = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 60}).json()
        assert job["status"] == "succeeded", job.get("error")
        assets = client.get(f"/songs/{song}/assets").json()
        master = next(
            a for a in assets
            if a["asset_type"] == "master" and a["generation_job_id"] == job["id"]
        )
        blob = client.get(f"/songs/{song}/assets/{master['id']}/download").content
        return job, assets, hashlib.sha256(blob).hexdigest()

    try:
        job, assets, h1 = render_hash(99)
        kinds = {a["asset_type"] for a in assets}
        need = {"take_stem", "role_stem", "stem_lead_vocal", "stem_gang_vocal",
                "vocal_bus", "mix", "master"}
        got = f"{len(need & kinds)}/{len(need)} kinds"
        rows.append(("Render -> isolated + combined stems", need <= kinds, got))

        takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
        counts = {}
        for t in takes:
            counts[t["singer_id"]] = counts.get(t["singer_id"], 0) + 1
        gang_ok = (
            counts.get(singers["Brian"]) == 8  # 7 gang + 1 lead
            and counts.get(singers["Pete"]) == 2
            and counts.get(singers["Brad"]) == 1
        )
        rows.append(("Gang 70/20/10 @ 10 -> 7/2/1 takes rendered", gang_ok, f"{len(takes)} takes"))

        _, _, h1b = render_hash(99)
        _, _, h3 = render_hash(1234)
        rows.append(("Re-render from same seed -> identical bytes", h1 == h1b, "master sha256"))
        rows.append(("Different seed -> different render", h1 != h3, "master sha256"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Section render", False, repr(exc)))

    return rows


STAGES = {"0": stage0, "1": stage1, "2": stage2}


def main() -> int:
    _isolated_env()
    stage = sys.argv[1] if len(sys.argv) > 1 else max(STAGES)
    if stage not in STAGES:
        print(f"stage {stage} gate not implemented; available: {sorted(STAGES)}")
        return 2

    client = _client()
    rows = STAGES[stage](client)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=REPO, capture_output=True, text=True
    )
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "no output"
    rows.append(("Automated test suite passes", proc.returncode == 0, last))

    width = max(len(name) for name, _, _ in rows)
    print(f"\nSTAGE {stage} EXIT CRITERIA\n{'=' * (width + 30)}")
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  | {detail}")
    passed = all(ok for _, ok, _ in rows)
    verdict = "ALL CRITERIA PASS" if passed else f"STAGE {stage} NOT COMPLETE"
    print(f"{'=' * (width + 30)}\n{verdict}\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
