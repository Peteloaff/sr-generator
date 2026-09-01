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

## [x] Stage 5 — Stem Separation + Song Editing

- [x] `StemSeparationProvider` — `CenterSplitStemProvider` (real, dependency-free
      center-channel separation), `MockStemProvider`, `HttpStemProvider` (Demucs
      service). Contract: `separate(source_path) -> StemSeparation`.
- [x] `POST /songs/{id}/separate` → song-level `stem_lead_vocal` +
      `stem_instrumental`, versioned (re-separate bumps the version)
- [x] `POST /sections/{id}/use-derived-stems` — slices the separated stems into a
      section's guide vocal + instrumental bed (feeds the Stage 3 conversion +
      Stage 2 mix)
- [x] `assemble_song` job — full-song mix = original recording with rendered
      sections spliced in (short crossfades); **untouched ranges byte-identical**
- [x] web: Cover Studio (separate / assemble) + per-section "Use separated stems"

**Exit criteria** — import a demo, isolate practical stems, replace one vocal
section, export a new mix without touching unrelated sections.
**All PASS** (`python scripts/stage_gate.py 5`). This is the "replace vocals on a
cover, keep the melody" workflow.

---

## [x] Stage 6 — Band DNA Analysis

- [x] reference library + **folder import** (`POST /bands/{id}/references/import-folder`,
      `scripts/import_catalogue.py`) — content-hash dedup, one job per catalogue
- [x] `LocalMirAnalysisProvider` (NumPy): BPM, key, tuning, energy curve,
      loudness, section structure, spectral embedding. `HttpAnalysisProvider` stub.
- [x] `sr/services/quality.py` — clipping / silence / too-short / mono / low-loudness
      flags → score + pass/fail; can't approve until analysed
- [x] `dataset_version` — deterministic hash of the approved set + analysis
      versions; `GET /bands/{id}/training-manifest` refuses (409) incomplete
      metadata; `POST` snapshots to `models/band/{id}/manifest_vN.json`
- [x] `GET /bands/{id}/dna` — BPM/key/tuning distributions, tag cloud, mean
      embedding, energy profile
- [x] web: Band DNA page (folder import, list, approve, DNA card, manifest)

**Exit criteria** — every approved training song has complete metadata and a
reproducible dataset manifest. **All PASS** (`python scripts/stage_gate.py 6`).

---

## [x] Stage 7 — Band-Specific Music Generation

- [x] `MusicGenerationProvider` contract (`generate` + optional `train_adapter`);
      `LocalSynthMusicProvider` — deterministic NumPy instrumental engine
      (`sr/common/musicgen.py`: kick/snare/hat, diatonic progression, bass, pads,
      arp, tonic drone) that trains adapters; `HttpMusicProvider` (real generative
      service: `POST /generate`, `POST /train-adapter`); `MockMusicProvider`
- [x] `BandAdapter` — `train_band_adapter` job distils the approved Band DNA
      (strict manifest + `band_dna`) into character / tempo-prior / key-prior /
      energy-profile, stored with its `dataset_version`
- [x] `generate_instrumental` job — `POST /songs/{id}/sections/{sid}/generate-instrumental`;
      resolves bpm/key (request override > song > adapter prior), renders a
      section bed, replaces the section's `instrumental_bed`, full lineage in the
      job metadata (child seed + every applied value)
- [x] web: Band DNA page trains / lists / deletes adapters; section panel picks an
      adapter and generates the bed, which then feeds the Stage 2/3 render

**Exit criteria** — repeatable instrumental sections useful for the band
workflow, with zero UI coupling to the model. **All PASS**
(`python scripts/stage_gate.py 7`). The synth engine is a deterministic stand-in
for a real generative model — `SR_MUSIC_PROVIDER=http` swaps it with no API
change (see MODEL_SETUP.md). Text-prompt full-song generation is Stage 8.

---

## [x] Stage 8 — Full Song Generator

- [x] deterministic **song planner** (`sr/services/songplan.py`): prompt (+ optional
      lyrics + Band DNA + seed) → structure template, per-section bars / seconds /
      energy / key, lyric-line distribution, and a default vocal arrangement
- [x] **`generate_full_song`** job — creates the sections, roles and lyric lines,
      then per section: a generated instrumental bed (Stage 7), a deterministic
      **guide melody** (`sr/common/guide.py`), and a full layering-engine render
      (Stages 2–4); concatenates the section renders into song-level
      `stem_instrumental` / `vocal_bus` / `song_mix` / `song_master`
- [x] `POST /songs/{id}/generate`, `GET /songs/{id}/plan` (dry run), wired into
      the existing section + Vocal Director machinery
- [x] web: "Full song generator" panel on the song page

**Exit criteria** — generate a complete project with independently editable
sections and singer assignments; output is never a single opaque file. **All
PASS** (`python scripts/stage_gate.py 8`). Every section, role, take, stem and the
song master is a separate `AudioAsset`; a single section re-renders on its own
without touching the others.

---

## [x] Stage 9 — Surgical Regeneration

- [x] `SongSection.locked` + `SectionRevision` history (kind / roles snapshot /
      render job / `is_current`)
- [x] `POST /sections/{id}/regenerate` — full section re-render, new revision, the
      rest of the song untouched (section renders were already isolated)
- [x] `POST /roles/{id}/regenerate` — re-renders the section but perturbs **only**
      that role's plan seed (`role_seed_salt`), so every other role's stem comes
      out byte-identical; optional single-role **singer swap**
- [x] `GET /sections/{id}/revisions`, `POST /sections/{id}/rollback`,
      `POST /sections/{id}/lock`
- [x] web: "Surgical regeneration" controls in the section panel

**Exit criteria** — change one role or section without materially altering locked
sections. **All PASS** (`python scripts/stage_gate.py 9`).

---

## [x] Stage 10 — Intelligent Vocal Arranger

- [x] singer metadata: `range_low_midi` / `range_high_midi` / `preferred_roles` /
      `energy_fit` (user-entered, not measured)
- [x] section-energy analysis (`sr/services/arranger.py`) from the section's
      instrumental bed loudness, with a section-type fallback; lyric density
- [x] `GET /songs/{id}/arrangement/recommend` — lead / double / harmony /
      background / gang recommendations per section, each with a `confidence` and
      a plain-text `rationale`
- [x] `POST /songs/{id}/arrangement/apply` — **skips** any section that already has
      roles (or is locked) unless `overwrite: true` is passed
- [x] web: "Auto arranger" panel (recommend table + apply with an explicit
      replace checkbox)

**Exit criteria** — recommendation produces a complete editable vocal map and
never overwrites user assignments without an explicit action. **All PASS**
(`python scripts/stage_gate.py 10`).

---

## [x] Stage 11 — Experimental Vocal Morph / Timbre R&D

- [x] whole feature gated behind `SR_EXPERIMENTAL_MORPH` (off by default); every
      endpoint 403s when disabled; `GET /experimental` probe for the UI
- [x] `VocalMorph` + `POST /morphs/{id}/preview` — a time-varying crossfade
      (`linear` / `equal_power` / `scurve`) between two singers' section vocals,
      rendered as a **preview only**
- [x] quality flags (`sr/services/morph.py`): envelope-correlation
      (`poor_alignment`), seam energy jump, gross level — a low score marks the
      morph `usable: false`
- [x] `POST /morphs/{id}/commit` refuses an unusable morph (409)
- [x] web: "Vocal morph (experimental)" lane, shown only when the flag is on

**Exit criteria** — enabled only when technically reliable and consent
compatible; otherwise stays behind an experimental flag. **All PASS**
(`python scripts/stage_gate.py 11`). The morph never enters a section mix in this
stage — it is deliberately preview + quality-gate only.
