# SR Generator

A **private, local-first AI music workstation for one band**. Not a general Suno
clone — the entire design is organized around a **Vocal Director** that gives
deterministic, section- and line-level control over *which authorized singer
performs each vocal part*, with weighted ensembles, harmonies, doubles, gang
vocals, and screams.

> **Status: Stage 4 (Vocal-Stack Quality) complete.** Harmony intervals, a
> de-ess/EQ/compressor chain per role, savable presets, and an A/B that proves
> ensemble mode beats a naive gain stack. A guide vocal is converted into each
> singer's voice (Stage 3). No music model yet. See [ROADMAP.md](ROADMAP.md).

## What you can do today

- **Run more than one band.** Everything is scoped to a `Band`; a second band is
  one click, fully isolated. Default band auto-created.
- **Upload an existing demo / instrumental** (wav/mp3/flac/m4a/ogg — ffmpeg is
  bundled) and see its **waveform** with section overlays.
- **Mark sections** (verse / chorus / breakdown / …) and edit lyrics as a text
  block that becomes per-line rows.
- **Direct the vocals**: per section *or* per lyric line, add lead / double /
  harmony / background / gang / scream roles, assign singers with **weights** and
  **harmony intervals** (`+3`, `-12`), attach a de-ess / EQ / compressor chain,
  and see the live normalized split and ensemble take counts.
- **Save a stack as a preset** and drop it on any section; **Render A/B** to see
  ensemble mode measured against a naive gain stack (stereo width, L/R
  correlation, mono-compatibility).
- **Give each singer a voice**: upload training samples and run the analysis, or
  set the profile by hand (pitch / formant / brightness / breathiness /
  roughness). Training and generation are blocked until you grant consent.
- **Render a section**: upload one guide vocal and each singer with a ready voice
  model has it converted into their voice; or upload a real take per singer; or
  fall back to a placeholder. Hit Render → humanized per-take stems, grouped
  stems, a vocal bus, a section mix, and a master — players + WAV downloads +
  a take-by-take breakdown (`source: converted / upload / mock`). Same seed →
  identical bytes.
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
  api/          FastAPI app + routers (bands, singers, voice_models, songs, vocal, render, jobs)
  models/       SQLAlchemy ORM (the core data model)
  schemas/      Pydantic request/response models
  services/     normalization, layering, render, consent, cache, presets, project i/o
  providers/    ABCs + mock + local_dsp/http voice providers + registry
  worker/       job queue backends, runner, handlers, progress, RQ entrypoint
  orchestrator/ generation pipeline definition (stubs for now)
  common/       allocation, seeds, storage, resolver, audio, dsp, synth, voice, vocalfx
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
