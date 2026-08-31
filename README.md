# SR Generator

A **private, local-first AI music workstation for one band**. Not a general Suno
clone — the entire design is organized around a **Vocal Director** that gives
deterministic, section- and line-level control over *which authorized singer
performs each vocal part*, with weighted ensembles, harmonies, doubles, gang
vocals, and screams.

> **Status: Stage 0 (Foundation) complete.** No AI models yet — only mock
> providers. See [ROADMAP.md](ROADMAP.md) for the staged plan.

## What Stage 0 gives you

- FastAPI backend + SQLAlchemy/Alembic schema for all core entities
  (Singer, Project, Song, SongSection, **LyricLine**, VocalRole, VocalAssignment,
  BandReference, GenerationJob, AudioAsset).
- A job system: every audio/ML operation is a queued `GenerationJob` that records
  seed, parameters, provider version, input assets, logs, and output assets.
- Provider abstraction (music / voice / stem / analysis / mastering /
  transcription) with **mock implementations** that produce real silent WAVs.
- Deterministic **largest-remainder allocation** and **child-seed derivation**
  (the 70/20/10 → 7/2/1 rule).
- A Next.js app with CRUD for singers, songs, and jobs.

## Requirements

- Python 3.12+
- Node 20+ (for the web app)
- No database or Redis install needed for Stage 0 (SQLite + in-process queue).

## Quick start (Windows, native)

```powershell
.\scripts\setup.ps1      # venv + deps + .env + migrate
.\scripts\dev.ps1        # API on http://localhost:8000  (docs at /docs)
```

In a second terminal:

```powershell
cd apps\web
npm install
npm run dev              # UI on http://localhost:3000
```

## Verify the stage gate

```powershell
.\scripts\test.ps1                          # ruff + pytest
.\.venv\Scripts\python.exe scripts\stage_gate.py   # Stage 0 exit criteria PASS/FAIL
```

## Repository layout

```
sr/
  api/          FastAPI app + routers
  models/       SQLAlchemy ORM (the core data model)
  schemas/      Pydantic request/response models
  providers/    provider ABCs + mock implementations + registry
  worker/       job queue backends, runner, handlers, RQ entrypoint
  orchestrator/ generation pipeline definition (stubs for now)
  common/       allocation, seed derivation, storage, role resolver
alembic/        migrations
apps/web/       Next.js UI
scripts/        setup / dev / worker / test / stage_gate
storage/        local audio assets (references, training, generated, stems)
```

## Docs

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | services, data flow, provider contracts, jobs |
| [ROADMAP.md](ROADMAP.md) | the 12-stage plan with status checkboxes |
| [MODEL_SETUP.md](MODEL_SETUP.md) | providers and GPU/setup instructions |
| [DATASET_GUIDE.md](DATASET_GUIDE.md) | reference-song & singer-sample requirements, consent |
| [TEST_PLAN.md](TEST_PLAN.md) | acceptance tests and audio evaluation protocol |
| [DECISIONS.md](DECISIONS.md) | architecture decision records |
| [CHANGELOG.md](CHANGELOG.md) | meaningful product changes |
