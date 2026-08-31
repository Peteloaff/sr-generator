"""Stage gate: check the current stage's exit criteria and print PASS/FAIL.

Usage:  python scripts/stage_gate.py            # current stage (0)
Exits non-zero if any criterion fails - do not proceed to the next stage.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _isolated_env() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sr-gate-"))
    os.environ["SR_DATABASE_URL"] = f"sqlite:///{(tmp / 'gate.db').as_posix()}"
    os.environ["SR_STORAGE_ROOT"] = tmp.as_posix()
    os.environ["SR_QUEUE_BACKEND"] = "inline"
    os.environ["SR_LOG_LEVEL"] = "WARNING"


def stage0() -> list[tuple[str, bool, str]]:
    from fastapi.testclient import TestClient

    from sr.api.main import create_app
    from sr.db import engine
    from sr.models import Base

    Base.metadata.create_all(engine)
    results: list[tuple[str, bool, str]] = []
    client = TestClient(create_app())

    # 1. stack boots + health
    h = client.get("/health").json()
    results.append(
        ("Stack boots locally (API + DB + providers)", h["status"] == "ok", str(h["status"]))
    )

    # 2. CRUD for singers / projects / songs
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
        results.append(
            ("CRUD for singers / projects / songs", ok, "create/read/update/delete cycle")
        )
    except Exception as exc:  # noqa: BLE001
        results.append(("CRUD for singers / projects / songs", False, repr(exc)))

    # 3. mocked generation job queued -> completed with asset + lineage
    try:
        job = client.post(
            "/jobs",
            json={
                "job_type": "mock_generation",
                "seed": 7,
                "parameters": {"prompt": "gate", "duration": 1.0},
            },
        ).json()
        done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 20}).json()
        ok = (
            done["status"] == "succeeded"
            and len(done["outputs"]) == 1
            and done["outputs"][0]["generation_job_id"] == done["id"]
            and done["provider_version"]
        )
        results.append(
            ("Mock generation job queued -> completed (with lineage)", bool(ok), done["status"])
        )
    except Exception as exc:  # noqa: BLE001
        results.append(("Mock generation job queued -> completed (with lineage)", False, repr(exc)))

    # 4. test suite passes
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=REPO, capture_output=True, text=True
    )
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "no output"
    results.append(("Automated test suite passes", proc.returncode == 0, last))

    return results


def main() -> int:
    _isolated_env()
    stage = sys.argv[1] if len(sys.argv) > 1 else "0"
    if stage != "0":
        print(f"stage {stage} gate not implemented yet")
        return 2

    rows = stage0()
    width = max(len(name) for name, _, _ in rows)
    print(f"\nSTAGE 0 EXIT CRITERIA\n{'=' * (width + 30)}")
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  | {detail}")
    passed = all(ok for _, ok, _ in rows)
    print(f"{'=' * (width + 30)}\n{'ALL CRITERIA PASS' if passed else 'STAGE 0 NOT COMPLETE'}\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
