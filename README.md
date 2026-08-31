# SR Generator

A **private, local-first AI music workstation for one band**. Not a general Suno
clone — the entire design is organized around a **Vocal Director** that gives
deterministic, section- and line-level control over *which authorized singer
performs each vocal part*, with weighted ensembles, harmonies, doubles, gang
vocals, and screams.

> **Status: Stage 7 (Band-Specific Music Generation) complete.** A band adapter
> is distilled from the approved Band DNA, and the music provider renders a
> deterministic, tempo/key-locked instrumental bed per section that band vocals
> render over. The generator is a NumPy synth engine standing in for a real
> model — `SR_MUSIC_PROVIDER=http` swaps it with no API change. Stages 1–6
> (workspace, layering, voice conversion, stack quality, stem separation, Band
> DNA) underneath. See [ROADMAP.md](ROADMAP.md).

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
- **Cover a song**: upload the mix, hit **Separate stems**, per section click
  **Use separated stems** (the separated vocal becomes the guide, the
  instrumental the bed), render with your singers, then **Assemble full mix** —
  the sections you didn't touch come out exactly as they were recorded.
- **Build the Band DNA**: point at a folder of your catalogue
  (`scripts/import_catalogue.py "D:/music/my band"` or the Band DNA page) — every
  track is analysed (BPM / key / tuning / structure / energy), quality-checked,
  and, once approved, rolled into a **reproducible training manifest** (refuses
  incomplete metadata).
- **Generate a band instrumental**: on the Band DNA page, **Train band adapter**
  from the approved catalogue; then on any section pick the adapter and
  **Generate instrumental** — a deterministic bed locked to the song's tempo and
  key, which the vocal render then mixes over. Same seed → identical bytes.
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
  api/          FastAPI app + routers (bands, singers, voice_models, songs, vocal, render, music, jobs)
  models/       SQLAlchemy ORM (the core data model)
  schemas/      Pydantic request/response models
  services/     layering, render, consent, cache, presets, separation, assembly, references, manifest, dna, quality, music
  providers/    ABCs + mock + local/http voice / stem / analysis / music providers + registry
  worker/       job queue backends, runner, handlers, progress, RQ entrypoint
  orchestrator/ generation pipeline definition (stubs for now)
  common/       allocation, seeds, storage, resolver, audio, dsp, synth, voice, vocalfx, separation, analysis, musicgen
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
