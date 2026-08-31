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


def _guide_bytes(seconds: float = 3.0, rate: int = 44100) -> bytes:
    import numpy as np
    import soundfile as sf

    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    mel = np.zeros_like(t)
    for i, f in enumerate([180.0, 220.0, 200.0, 247.0, 180.0]):
        seg = (t >= i * 0.6) & (t < (i + 1) * 0.6)
        mel[seg] = np.sin(2 * np.pi * f * t[seg])
    am = 0.4 + 0.6 * np.clip(np.sin(2 * np.pi * 3 * t) ** 2, 0.0, 1.0)
    buf = io.BytesIO()
    sf.write(buf, (0.4 * mel * am).astype("float32"), rate, format="WAV")
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
    singers = {}
    for n in ("Brian", "Pete", "Brad"):
        sid = client.post("/singers", json={"name": n}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        singers[n] = sid
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


def stage3(client) -> list[Row]:
    import hashlib

    rows: list[Row] = []
    guide = _guide_bytes()

    singers = {}
    for name, prof in (
        ("Brian", {"median_f0": 110.0, "brightness": -0.5}),
        ("Pete", {"median_f0": 250.0, "brightness": 0.4, "breathiness": 0.3}),
    ):
        sid = client.post("/singers", json={"name": name}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        client.patch(f"/singers/{sid}/voice-model", json=prof)
        singers[name] = sid

    song = client.post("/songs", json={"title": "Gate S3", "seed": 7}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "verse", "start_time": 0, "end_time": 3},
    ).json()["id"]
    for name in ("Brian", "Pete"):
        client.post(
            f"/sections/{section}/roles",
            json={"role_type": "lead", "assignments": [{"singer_id": singers[name]}]},
        )
    client.post(
        f"/songs/{song}/sections/{section}/guide",
        files={"file": ("g.wav", guide, "audio/wav")},
    )

    def render_once(seed):
        job = client.post(
            f"/songs/{song}/sections/{section}/render", json={"seed": seed}
        ).json()
        job = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 90}).json()
        assert job["status"] == "succeeded", job.get("error")
        return job

    try:
        job = render_once(7)
        takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
        converted = all(t["source_kind"] == "converted" for t in takes) and len(takes) >= 2
        rows.append(("Guide converted per singer via VoiceProvider", converted,
                     f"{len(takes)} takes, all converted"))

        stems = {
            a["singer_id"]: a["id"]
            for a in client.get(f"/songs/{song}/assets").json()
            if a["asset_type"] == "take_stem"
        }
        b = client.get(f"/songs/{song}/assets/{stems[singers['Brian']]}/download").content
        p = client.get(f"/songs/{song}/assets/{stems[singers['Pete']]}/download").content
        indep = b != p and len(b) > 1000
        rows.append(("Each singer is an independent rendering", indep, "stems differ"))

        def master_hash(seed):
            j = render_once(seed)
            m = next(a for a in client.get(f"/songs/{song}/assets").json()
                     if a["asset_type"] == "master" and a["generation_job_id"] == j["id"])
            return hashlib.sha256(
                client.get(f"/songs/{song}/assets/{m['id']}/download").content
            ).hexdigest()

        repeatable = master_hash(7) == master_hash(7)
        rows.append(("Conversion render is repeatable", repeatable, "master sha256"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("Voice conversion render", False, repr(exc)))

    # consent gate
    try:
        blocked = client.post("/singers", json={"name": "NoConsent"}).json()["id"]
        client.patch(f"/singers/{blocked}/voice-model", json={"median_f0": 200.0})
        s2 = client.post("/songs", json={"title": "x"}).json()["id"]
        sec2 = client.post(f"/songs/{s2}/sections", json={"section_type": "verse"}).json()["id"]
        client.post(
            f"/sections/{sec2}/roles",
            json={"role_type": "lead", "assignments": [{"singer_id": blocked}]},
        )
        r = client.post(f"/songs/{s2}/sections/{sec2}/render", json={})
        rows.append(
            ("Render blocked without consent_generation", r.status_code == 403, str(r.status_code))
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(("Consent gate", False, repr(exc)))

    return rows


def stage4(client) -> list[Row]:
    rows: list[Row] = []
    singers = {}
    for n in ("Brian", "Pete", "Brad"):
        sid = client.post("/singers", json={"name": n}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        singers[n] = sid
    song = client.post("/songs", json={"title": "Gate S4", "seed": 42}).json()["id"]
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
            "role_type": "gang", "ensemble_size": 12, "width": 90,
            "humanize_timing_ms": 22, "humanize_pitch_cents": 9,
            "processing": [{"type": "deesser", "amount": 0.4}, {"type": "compressor", "ratio": 3}],
            "assignments": [
                {"singer_id": singers["Brian"], "weight_percent": 50},
                {"singer_id": singers["Pete"], "weight_percent": 30},
                {"singer_id": singers["Brad"], "weight_percent": 20},
            ],
        },
    )
    harm = client.post(
        f"/sections/{section}/roles",
        json={
            "role_type": "harmony", "ensemble_size": 2, "humanize_pitch_cents": 0,
            "assignments": [
                {"singer_id": singers["Pete"], "weight_percent": 50, "interval_semitones": 3},
                {"singer_id": singers["Brad"], "weight_percent": 50, "interval_semitones": 7},
            ],
        },
    ).json()

    try:
        ab = client.post(f"/songs/{song}/sections/{section}/ab", json={}).json()
        v = ab["verdict"]
        rows.append(
            ("A/B: ensemble clearly different from flat gain-mix",
             bool(v["ensemble_clearly_different"]),
             f"width +{v['width_gain']}, corr {ab['ensemble']['stereo_correlation']}")
        )
        rows.append(
            ("No phase collapse in the ensemble stack",
             ab["ensemble"]["mono_compat"] > 0.5,
             f"mono_compat {ab['ensemble']['mono_compat']}")
        )
        takes = client.get(f"/songs/{song}/renders/{ab['ensemble_job_id']}/takes").json()
        ta = [a for a in client.get(f"/songs/{song}/assets").json()
              if a["asset_type"] == "take_stem"]
        wav = client.get(f"/songs/{song}/assets/{ta[0]['id']}/download").content
        rows.append(
            ("Individual takes remain exportable",
             len(ta) >= len(takes) > 0 and wav[:4] == b"RIFF", f"{len(ta)} take stems")
        )
        hp = {t["singer_id"]: t["pitch_cents"]
              for t in takes if t["vocal_role_id"] == harm["id"]}
        ok = (abs(hp.get(singers["Pete"], 0) - 300) < 2
              and abs(hp.get(singers["Brad"], 0) - 700) < 2)
        rows.append(("Harmony intervals land at the right pitch", ok, str(sorted(hp.values()))))
    except Exception as exc:  # noqa: BLE001
        rows.append(("A/B render", False, repr(exc)))

    try:
        p = client.post(
            "/vocal-presets", json={"name": "Gate Big Chorus", "from_section_id": section}
        ).json()
        sec2 = client.post(f"/songs/{song}/sections", json={"section_type": "bridge"}).json()["id"]
        res = client.post(f"/vocal-presets/{p['id']}/apply", json={"section_id": sec2}).json()
        rows.append(
            ("Vocal preset saves + applies to another section",
             len(res["created_roles"]) == 3 and res["skipped_singers"] == [],
             f"{len(res['created_roles'])} roles")
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(("Vocal presets", False, repr(exc)))

    return rows


def stage5(client) -> list[Row]:
    import numpy as np
    import soundfile as sf

    rows: list[Row] = []
    sr = 44100
    t = np.linspace(0, 12, sr * 12, endpoint=False)
    voc = np.zeros_like(t)
    for i, f in enumerate([220, 247, 262, 294, 262, 247, 220, 196]):
        seg = (t >= i * 1.5) & (t < (i + 1) * 1.5)
        voc[seg] = 0.35 * np.sin(2 * np.pi * f * t[seg])
    li = 0.25 * np.sin(2 * np.pi * 110 * t)
    ri = 0.25 * np.sin(2 * np.pi * 110 * t + 0.5) + 0.15 * np.sin(2 * np.pi * 220 * t)
    buf = io.BytesIO()
    sf.write(buf, np.stack([voc + li, voc + ri], axis=1).astype("float32"), sr, format="WAV")
    cover = buf.getvalue()

    sid = client.post("/singers", json={"name": "Brian"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_generation": True})
    client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 130.0})
    song = client.post("/songs", json={"title": "Gate Cover", "seed": 5}).json()["id"]
    client.post(f"/songs/{song}/audio", files={"file": ("c.wav", cover, "audio/wav")})
    sec_a = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "verse", "start_time": 0, "end_time": 4},
    ).json()["id"]
    client.post(
        f"/songs/{song}/sections",
        json={"section_type": "chorus", "start_time": 4, "end_time": 8},
    )

    def _win(a, s, e):
        return a[int(s * sr) : int(e * sr)]

    try:
        j = client.post(f"/songs/{song}/separate").json()
        j = client.post(f"/jobs/{j['id']}/wait", params={"timeout": 120}).json()
        stems = client.get(f"/songs/{song}/stems").json()
        ok = j["status"] == "succeeded" and {s["asset_type"] for s in stems} == {
            "stem_lead_vocal", "stem_instrumental"
        }
        rows.append(("Separate a mix into vocal + instrumental stems", ok, f"{len(stems)} stems"))

        d = client.post(f"/songs/{song}/sections/{sec_a}/use-derived-stems").json()
        client.post(
            f"/sections/{sec_a}/roles",
            json={"role_type": "lead", "assignments": [{"singer_id": sid}]},
        )
        rj = client.post(f"/songs/{song}/sections/{sec_a}/render", json={}).json()
        rj = client.post(f"/jobs/{rj['id']}/wait", params={"timeout": 120}).json()
        rows.append(
            ("Wire separated stems into a section + render",
             {x["asset_type"] for x in d} == {"guide_vocal", "instrumental_bed"}
             and rj["status"] == "succeeded", "guide + bed + render")
        )

        aj = client.post(f"/songs/{song}/assemble").json()
        aj = client.post(f"/jobs/{aj['id']}/wait", params={"timeout": 120}).json()
        mix = client.get(f"/songs/{song}/mixes").json()[0]
        new_b = client.get(f"/songs/{song}/assets/{mix['id']}/download").content
        tmp = Path(tempfile.mkdtemp()) / "a.wav"
        tmp.write_bytes(new_b)
        new, _ = sf.read(tmp)

        from sr.common.storage import get_storage

        orig_path = next(
            p for p in get_storage().root.rglob("canonical.wav")
            if f"{song}/canonical.wav" in str(p).replace("\\", "/")
        )
        orig, _ = sf.read(orig_path)

        untouched = np.array_equal(_win(new, 5.0, 7.5), _win(orig, 5.0, 7.5))
        replaced = not np.allclose(_win(new, 1.0, 3.0), _win(orig, 1.0, 3.0), atol=1e-4)
        rows.append(("Assembled mix: replaced section differs", replaced, "section A"))
        rows.append(
            ("Assembled mix: untouched sections byte-identical", untouched, "section B window")
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(("Stem separation + assembly", False, repr(exc)))

    return rows


STAGES = {
    "0": stage0, "1": stage1, "2": stage2, "3": stage3, "4": stage4, "5": stage5,
}


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
