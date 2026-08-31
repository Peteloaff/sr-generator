# SR Generator

A **private, local-first AI music workstation for one band**. Not a general Suno
clone — the entire design is organized around a **Vocal Director** that gives
deterministic, section- and line-level control over *which authorized singer
performs each vocal part*, with weighted ensembles, harmonies, doubles, gang
vocals, and screams.

> **Status: Stage 2 (Audio Layering Engine) complete.** No AI models yet — source
> vocals are uploaded takes or deterministic placeholders. Load real music and
> singers once the framework is proven. See [ROADMAP.md](ROADMAP.md).

## What you can do today

- **Run more than one band.** Everything is scoped to a `Band`; a second band is
  one click, fully isolated. Default band auto-created.
- **Upload an existing demo / instrumental** (wav/mp3/flac/m4a/ogg — ffmpeg is
  bundled) and see its **waveform** with section overlays.
- **Mark sections** (verse / chorus / breakdown / …) and edit lyrics as a text
  block that becomes per-line rows.
- **Direct the vocals**: per section *or* per lyric line, add lead / double /
  harmony / background / gang / scream roles, assign singers with **weights**,
  and see the live normalized split and ensemble take counts
  (`Brian 70 → 7 takes`).
- **Render a section**: upload each singer's take (or use a placeholder), hit
  Render, and get humanized per-take stems, grouped stems, a vocal bus, a section
  mix, and a master — with players and WAV downloads, plus a take-by-take
  breakdown of every timing/pitch/pan variation. Same seed → identical bytes.
- **Export / import a project** as portable JSON — carry an arrangement to
  another band; singers are matched by name.

Underneath (from Stage 0): provider abstraction with mock implementations, a
queued job system with full lineage, deterministic largest-remainder allocation
and child-seed derivation.

## Requirements

- Python 3.12+
- Node 20+ (for the web app)
- No database, Redis, or ffmpeg install needed (SQLite + in-process queue +
  bundled ffmpeg).

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
.\scripts\test.ps1                                  # ruff + pytest
.\.venv\Scripts\python.exe scripts\stage_gate.py    # latest stage's exit criteria PASS/FAIL
.\.venv\Scripts\python.exe scripts\stage_gate.py 0  # a specific stage
```

## Repository layout

```
sr/
  api/          FastAPI app + routers (bands, singers, projects, songs, vocal, render, jobs)
  models/       SQLAlchemy ORM (the core data model)
  schemas/      Pydantic request/response models
  services/     vocal normalization, layering plan, section render, project i/o
  providers/    provider ABCs + mock implementations + registry
  worker/       job queue backends, runner, handlers, RQ entrypoint
  orchestrator/ generation pipeline definition (stubs for now)
  common/       allocation, seeds, storage, resolver, audio (ffmpeg), dsp, synth
alembic/        migrations
apps/web/       Next.js UI (band switcher, song workspace, Vocal Director)
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
