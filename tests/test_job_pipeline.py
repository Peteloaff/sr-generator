"""Stage 0 core: a mocked generation job can be queued and completed, with full
lineage (seed, params, provider version, logs, output assets)."""

from __future__ import annotations

from sr.db import session_scope
from sr.models.generation_job import GenerationJob
from sr.worker.runner import run_job


def test_mock_generation_job_completes_with_assets_and_lineage(client):
    song_id = client.post("/songs", json={"title": "J", "seed": 7}).json()["id"]

    created = client.post(
        "/jobs",
        json={
            "job_type": "mock_generation",
            "song_id": song_id,
            "seed": 7,
            "parameters": {"prompt": "big chorus", "duration": 3.0},
        },
    ).json()

    # eager queue: finished by the time POST returns
    assert created["status"] == "succeeded"
    assert created["provider"] == "mock"
    assert created["provider_version"].startswith("mock-")
    assert created["progress"] == 1.0
    assert created["seed"] == 7
    assert "big chorus" in created["logs"]
    assert len(created["outputs"]) == 1

    asset = created["outputs"][0]
    assert asset["asset_type"] == "section_render"
    assert asset["duration"] == 3.0
    assert asset["generation_job_id"] == created["id"]


def test_job_get_and_wait_endpoints(client):
    job = client.post("/jobs", json={"job_type": "mock_generation", "parameters": {}}).json()
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "succeeded"
    assert client.post(f"/jobs/{job['id']}/wait").json()["status"] == "succeeded"


def test_job_determinism_same_seed_same_output_path(client):
    def run(seed: int) -> str:
        j = client.post(
            "/jobs",
            json={"job_type": "mock_generation", "seed": seed, "parameters": {"prompt": "x"}},
        ).json()
        return j["outputs"][0]["file_path"]

    assert run(123) == run(123)
    assert run(123) != run(456)


def test_failed_job_is_safe_and_retryable(client):
    with session_scope() as db:
        job = GenerationJob(job_type="does_not_exist", status="queued", parameters_json={})
        db.add(job)
        db.flush()
        job_id = job.id

    status = run_job(job_id)
    assert status == "failed"

    with session_scope() as db:
        job = db.get(GenerationJob, job_id)
        assert job.error and "no handler" in job.error
        assert job.attempts == 1
        assert job.completed_at is not None

    r = client.post(f"/jobs/{job_id}/retry")
    assert r.status_code == 201 or r.status_code == 200
    with session_scope() as db:
        assert db.get(GenerationJob, job_id).attempts == 2
