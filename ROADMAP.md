# Roadmap

One stage at a time. Do not start a stage until the previous stage's automated
tests and exit criteria pass (`python scripts/stage_gate.py <N>`).

Legend: `[x]` done · `[~]` in progress · `[ ]` not started

---

## [x] Stage 0 — Foundation & Architecture

Clean repo + product skeleton, no AI generation.

- [x] Project scaffold, `.env`, scripts, optional `docker-compose.yml`
- [x] FastAPI API + SQLAlchemy/Alembic schema for all core entities
- [x] `LyricLine` entity + section/line vocal-role resolution
- [x] Redis-free job queue (`inline`) + RQ backend for parity
- [x] Provider ABCs + mock implementations + registry
- [x] Storage abstraction (local FS, S3-shaped)
- [x] Largest-remainder allocation + deterministic child seeds
- [x] Next.js app: CRUD for singers / songs / jobs
- [x] Test suite + `stage_gate.py`
- [x] Docs: README, ARCHITECTURE, ROADMAP, MODEL_SETUP, DATASET_GUIDE, TEST_PLAN, DECISIONS, CHANGELOG

**Exit criteria**

- [x] Entire stack boots locally
- [x] CRUD for singers / projects / songs works
- [x] A mocked generation job can be queued and completed (with lineage)
- [x] Test suite passes

---

## [x] Stage 1 — Singer Library + Existing-Song Workspace

Useful with uploaded audio, before any voice generation.

- [x] `Band` entity — everything scoped by `band_id`; a second band is one row
- [x] Audio upload + storage + `AudioAsset(asset_type=upload)` (bundled ffmpeg)
- [x] Waveform peaks endpoint + SVG display with section overlays
- [x] Section create / edit / reorder API + UI; lyric-line editor (text → lines)
- [x] Singer profile screens + consent fields (band-scoped)
- [x] VocalRole / VocalAssignment CRUD + live percentage normalization + take counts
- [x] Per-line vocal-role override (line overrides section) in the workspace
- [x] Project export / import — portable JSON snapshot, round-trips exactly

**Exit criteria** — upload a song, mark Verse/Chorus/Breakdown, assign singers
and vocal roles to every section (and override on specific lines), export →
import → identical. **All PASS** (`python scripts/stage_gate.py 1`).

---

## [x] Stage 2 — Vocal Director + Audio Layering Engine

Deterministic multi-singer orchestration on supplied/mock takes.

- [x] lead / double / harmony / background / gang / scream roles wired end to end
- [x] ensemble-size allocator drives per-take generation (`plan_role_takes`)
- [x] micro-variation engine — timing / pitch / formant / gain / pan from child
      seeds; every applied value stored as a `RenderTake` row
- [x] pure-numpy DSP (`sr/common/dsp.py`) + deterministic placeholder synth
- [x] `render_section` job: take stems → role stems → grouped stems → vocal bus →
      section mix → master, all with lineage
- [x] source-take + instrumental upload; WAV/stem download endpoint
- [x] web: per-section render panel with stem players, downloads, take breakdown

**Exit criteria** — given 3 singers' source takes, build a chorus with 70/20/10
gang allocation and export isolated + combined stems repeatably from a seed.
**All PASS** (`python scripts/stage_gate.py 2`).

---

## [x] Stage 3 — First Real Singing Voice Provider

- [x] `VoiceProvider` contract (`analyze` + `convert`); `LocalDspVoiceProvider`
      (real, dependency-free), `MockVoiceProvider`, `HttpVoiceProvider` (GPU service)
- [x] singer voice-model setup: sample upload → `train_singer` job → analysed
      profile; manual profile tuning
- [x] guide-vocal upload per section; render resolves upload → guide+model
      conversion → placeholder
- [x] pitch/timing preservation (transforms the guide itself), job progress,
      filesystem-first conversion cache, retry-safe
- [x] **consent enforcement** — render 403 / train fails without the flag
- [x] web: singer voice-model panel, section guide upload, `source: converted`

**Exit criteria** — one guide phrase renders as each singer independently and
assembles via the Vocal Director; deterministic; consent-gated.
**All PASS** (`python scripts/stage_gate.py 3`). Full audio-quality eval
protocol (intelligibility / alignment scoring) is deferred to a real neural
provider — see TEST_PLAN.md.

---

## [x] Stage 4 — Harmony / Double / Gang Vocal Quality

- [x] multi-take generation + humanization (Stage 2) + `VocalAssignment.interval_semitones`
      for harmony intervals and octave doubles
- [x] per-role processing chain (`sr/common/vocalfx.py`): de-esser, FFT EQ,
      compressor; stack-gain compensation (`1/√n`)
- [x] `VocalPreset` — save a section's stack, apply to any section (singers by name)
- [x] `render` `mode: ensemble | flat`; `POST /sections/{id}/ab` renders both and
      compares width / L-R correlation / mono-compatibility

**Exit criteria** — A/B shows a clear difference between a gain mix and ensemble
mode; no phase collapse; individual takes still exportable.
**All PASS** (`python scripts/stage_gate.py 4`).

---

## [ ] Stage 5 — Stem Separation + Song Editing

- [ ] `StemSeparationProvider`; import full mix → derive stems
- [ ] replace/regenerate vocal layers; preserve original instrumental; versioned assets

**Exit criteria** — import a demo, isolate practical stems, replace one vocal
section, export a new mix without touching unrelated sections.

---

## [ ] Stage 6 — Band DNA Analysis

- [ ] reference library; BPM/key/structure/tuning metadata; tags; embeddings
- [ ] dataset approval flags; quality checks; training-manifest generator

**Exit criteria** — every approved training song has complete metadata and a
reproducible dataset manifest.

---

## [ ] Stage 7 — Band-Specific Music Generation R&D

- [ ] `MusicGenerationProvider` (ACE-Step-class or best current option)
- [ ] text/reference generation; adapter/LoRA training job; generation metadata

**Exit criteria** — repeatable instrumental sections useful for the band
workflow, with zero UI coupling to the model.

---

## [ ] Stage 8 — Full Song Generator

- [ ] prompt → lyrics → structure planner → section music → guide melody → vocals → mix → export
- [ ] wired into existing sections + Vocal Director

**Exit criteria** — generate a complete project with independently editable
sections and singer assignments; output is never a single opaque file.

---

## [ ] Stage 9 — Surgical Regeneration

- [ ] regenerate chorus only / one layer only / swap singer only
- [ ] preserve timing + project context; asset versioning; undo/rollback

**Exit criteria** — change one role or section without materially altering locked
sections.

---

## [ ] Stage 10 — Intelligent Vocal Arranger

- [ ] singer preference/range metadata; section-energy analysis
- [ ] recommended roles + confidence; one-click apply; manual override

**Exit criteria** — recommendation produces a complete editable vocal map and
never overwrites user assignments without an explicit action.

---

## [ ] Stage 11 — Experimental Vocal Morph / Timbre R&D

- [ ] morph automation lane; provider experiments; quality flags; render previews

**Exit criteria** — enabled only when technically reliable and consent
compatible; otherwise stays behind an experimental flag.
