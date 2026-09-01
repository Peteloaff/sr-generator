# SR Generator

A **private, local-first AI music workstation for one band**. Not a general Suno
clone — the entire design is organized around a **Vocal Director** that gives
deterministic, section- and line-level control over *which authorized singer
performs each vocal part*, with weighted ensembles, harmonies, doubles, gang
vocals, and screams.

> **Status: Stages 0–11 complete — the full roadmap.** A prompt becomes a
> structured, editable project: a deterministic song plan, a per-section
> instrumental + guide melody, layered band vocals, and song stems + a master
> (Stage 8). Any section, layer, or singer regenerates in isolation with a
> revision history and rollback (Stage 9). The arranger recommends a complete,
> editable vocal map from singer metadata and section energy without ever
> clobbering manual work (Stage 10). Experimental singer-to-singer morphing lives
> behind `SR_EXPERIMENTAL_MORPH` with an honest quality gate (Stage 11). Every
> model remains a swappable provider. The web app is a guided
> **Create → Story → Cast → Studio** flow, and you can record your own voice
> from the browser microphone to sing on a song. See [ROADMAP.md](ROADMAP.md).

## What you can do today

- **Create a song from the home page.** Title + style chips + a free-text prompt
  drop you straight into a guided **Story → Cast → Studio** workspace: write the
  lyrics and style, cast singers on every section, then generate and listen.
- **Record your own voice from the browser.** "Add your voice" on the Singers
  page (or from the Cast step) opens a mic recorder — record a few takes, train,
  and your voice is a normal singer you can assign to any role in any song.
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
- **Give each singer a voice**: record or upload training samples and run the
  analysis, or set the profile by hand (pitch / formant / brightness /
  breathiness / roughness). Training and generation are blocked until you grant
  consent.
- **Render a section**: upload one guide vocal and each singer with a ready voice
  model has it converted into their voice; or upload a real take per singer; or
  fall back to a placeholder. Hit Render → humanized per-take stems, grouped
  stems, a vocal bus, a section mix, and a master — players + WAV downloads +
  a take-by-take breakdown (`source: converted / upload / mock`). Same seed →
  identical bytes.
- **Generate a whole song from a prompt**: "Compose → Generate song" builds the
  structure, a default arrangement, a per-section instrumental + guide melody,
  renders the band vocals, and produces song stems + a master. It's a normal
  editable project, not one opaque file. Same seed → identical song master.
- **Surgically regenerate**: lock the sections you like, then regenerate one
  section, one layer (gang only, harmony only, …), or swap a single singer — the
  other layers come out byte-identical. Every regeneration is a revision you can
  **roll back**.
- **Auto-arrange**: fill in each singer's preferred roles / range / energy fit,
  then "Recommend arrangement" for a complete lead/double/harmony/gang map with
  confidence and reasons. Apply skips sections that already have roles unless you
  tick "replace".
- **(Experimental) Vocal morph**: with `SR_EXPERIMENTAL_MORPH=true`, preview an
  automated transition from one singer to another across a section; the preview
  is quality-scored and an unreliable one can't be committed.
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
  api/          FastAPI app + routers (…, music, compose, regen, arranger, morph, jobs)
  models/       SQLAlchemy ORM (the core data model)
  schemas/      Pydantic request/response models
  services/     layering, render, consent, cache, presets, separation, assembly, references,
                manifest, dna, quality, music, songplan, fullsong, regen, arranger, morph
  providers/    ABCs + mock + local/http voice / stem / analysis / music providers + registry
  worker/       job queue backends, runner, handlers, progress, RQ entrypoint
  orchestrator/ generation pipeline definition (stubs for now)
  common/       allocation, seeds, storage, resolver, audio, dsp, synth, voice, vocalfx,
                separation, analysis, musicgen, guide
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
