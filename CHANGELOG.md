# Changelog

## [Stage 4] — Vocal-Stack Quality — 2026-08-31

Stacks now sound produced, not copied.

### Added
- **Harmony intervals**: `VocalAssignment.interval_semitones` — a harmony singer
  at `+3`/`+7`, an octave double at `-12`. Layered into the take pitch alongside
  detune + jitter; kept even in `flat` mode (it's arrangement, not production).
- **`sr/common/vocalfx.py`**: de-esser (dynamic HF duck), full-signal FFT EQ
  (two shelves + presence bell), soft-knee compressor, `stack_gain(n)=1/√n`
  compensation, and A/B metrics (`stereo_correlation`, `width_ratio`,
  `mono_compat`). A per-role chain lives in `VocalRole.processing_json` and runs
  on the summed role stem.
- **`VocalPreset`** (band-scoped): capture a section's roles (singers by name +
  weight + interval + mix + processing), apply to any section.
  `POST/GET/DELETE /vocal-presets`, `POST /vocal-presets/{id}/apply`.
- **A/B render**: `RenderRequest.mode` (`ensemble` default / `flat`).
  `POST /songs/{id}/sections/{sid}/ab` renders both and returns a verdict —
  ensemble measurably wider, less L-R correlated, no phase collapse.
- `GenerationJob.result_json` persists a job's result metadata (incl. A/B
  numbers).
- **Web**: interval field per harmony/double singer; per-role fx chain editor;
  ensemble size/width inline; "Save section as preset" / "Apply preset";
  "Render A/B" with the width/correlation table and both masters.
- 20 new tests (112 total); `stage_gate.py 4`.

### Fixed
- `plan_role_takes` local `flat` list shadowed the new `flat` parameter — would
  have disabled all humanisation. Renamed to `take_order`.

---

## [Stage 3] — Singing Voice Provider — 2026-08-31

A guide vocal is now converted into each singer's voice. The conversion is real
DSP (dependency-free); a neural model implements the same contract.

### Added
- **`VoiceProvider` contract** (`analyze(samples)` + `convert(guide, profile,
  seed)`). Implementations: `LocalDspVoiceProvider` (default — pitch to register,
  STFT formant warp, spectral tilt, breath, drive), `MockVoiceProvider` (fast
  detune, tests), `HttpVoiceProvider` (POSTs to `SR_VOICE_HTTP_URL` — a local or
  remote GPU model service).
- **`sr/common/voice.py`**: `estimate_f0`, `analyze` → `VoiceProfile`
  (median_f0 / formant / brightness / breathiness / roughness), `convert`.
- **Singer voice model**: `Singer.voice_profile_json`; `POST /singers/{id}/samples`,
  `train_singer` job (analyses samples → profile → `training_status=ready`),
  `GET/PATCH /singers/{id}/voice-model` (manual tuning).
- **Guide vocal**: `POST /songs/{id}/sections/{sid}/guide`. Render resolution
  order per singer: uploaded take → guide + ready voice model (converted, cached)
  → deterministic placeholder.
- **Consent enforcement** (`sr/services/consent.py`): render is **403** if any
  assigned singer lacks `consent_generation`; `train_singer` fails without
  `consent_training`. Enforced at the API and again in the job.
- **`RenderCache`** — voice conversions are filesystem-addressed (`cache/…`),
  written before the render commits, so a retry after a rollback reuses them.
- **Job progress** — `job.progress` advances through a render.
- **Web**: singer voice-model panel (samples, train, profile sliders); section
  guide-vocal upload; take breakdown shows `source: converted`.
- 15 new tests (79 total); `stage_gate.py 3`.

### Changed
- `VoiceProvider.render()` replaced by `analyze()` + `convert()`.
- `run_job` progress/cache use the handler's own session (SQLite single-writer
  cannot grant a concurrent write transaction).
- `render_voice` job type removed (voice rendering happens inside `render_section`).
- `dsp._resample` → `dsp.resample` (public). Default `SR_VOICE_PROVIDER=local_dsp`.

---

## [Stage 2] — Audio Layering Engine — 2026-08-31

The Vocal Director's definitions now render into real, humanized, mixed audio.
Still no AI models: source vocals are uploaded takes or deterministic
placeholders.

### Added
- **Micro-variation engine** (`sr/services/layering.py`): `plan_role_takes(role,
  seed)` → one `TakeSpec` per virtual performance, with largest-remainder
  allocation and bounded timing/pitch/formant/gain/pan variation from per-take
  child seeds, plus deterministic stereo spread from `role.width`.
- **`RenderTake` model**: every take's child seed and applied variation values,
  with source + output asset links — a render can be reconstructed take-for-take.
- **DSP** (`sr/common/dsp.py`, pure NumPy): gain, equal-power pan,
  sample-accurate timing offset, resample-based pitch shift, spectral-tilt
  formant, sum/normalize. **Synth** (`sr/common/synth.py`): distinct deterministic
  placeholder vocal per singer.
- **`render_section` job** (`sr/services/render.py`): take stems → role stems →
  grouped stems (`stem_lead_vocal` / `stem_background_vocal` / `stem_gang_vocal`)
  → `vocal_bus` → `mix` (+ optional instrumental) → `master`. Every artifact is an
  `AudioAsset` with parent/job lineage; the whole render is one transaction.
- **API**: `POST /songs/{id}/sections/{sid}/takes` (source take per singer),
  `.../instrumental`, `.../render`, `GET .../renders`, `GET .../renders/{job}/takes`,
  `GET /songs/{id}/assets/{aid}/download` (WAV export).
- `AudioAsset` gains `singer_id` and `label`.
- **Web**: per-section render panel — upload takes, "Render section", inline stem
  players + downloads, and the take-by-take variation breakdown.
- 16 new tests (64 total); `stage_gate.py 2`.

### Changed
- Job handlers now take `(job, db)`; `run_job` uses three transactions so a failed
  render still records its attempt + error.
- `derive_seed` masked to 63 bits (fits signed BIGINT / numpy int64 everywhere).
- A stale `X-Band-Id` header falls back to the default band (an explicit
  `?band_id=` still 404s).

---

## [Stage 1] — Singer Library + Song Workspace — 2026-08-31

Still no AI models — mock providers only. The app is now useful for directing
vocals on existing audio.

### Added
- **`Band` entity** — `Singer` / `Project` / `Song` / `BandReference` are scoped
  by `band_id`; default band auto-created; active band via `?band_id=`,
  `X-Band-Id` header, or default. Singer names unique per band. (`/bands` CRUD +
  `/bands/{id}/stats`.)
- **Audio pipeline** (`sr/common/audio.py`) using ffmpeg bundled with
  `imageio-ffmpeg`: probe duration/SR/channels, transcode to canonical WAV,
  downsampled waveform peaks. `POST /songs/{id}/audio` (wav/mp3/flac/m4a/ogg/…),
  `GET /songs/{id}/assets/{id}/waveform`.
- **Section editing**: `PATCH` section, `PUT /sections/reorder`.
- **Lyric-line editing**: `PATCH` line, `PUT /songs/{id}/lines` (rebuild from a
  text block).
- **Vocal Director API** (`sr/api/routers/vocal.py`): vocal role + assignment
  CRUD on sections and lines; `GET /roles/{id}/normalized` returns the
  100%-scaled split and the largest-remainder ensemble take counts
  (70/20/10 @ 10 → 7/2/1). Cross-band singer assignments rejected.
- **Project export / import** (`sr/services/project_io.py`): portable JSON
  snapshot (sections, lines, roles, weights, seeds, gains, pans, humanization),
  singers referenced by name. Importing into another band recreates placeholder
  singers (consent flags false).
- **Web workspace**: band switcher; song page with audio upload, SVG waveform +
  section overlays, section table (type/name/times/reorder), lyrics editor,
  per-section and per-line Vocal Director panels with live take counts; projects
  page with export download / import upload.
- Migrations squashed to one `initial schema (through stage 1)` revision
  (ADR-0008).
- 19 new tests (48 total); `stage_gate.py 1`.

### Changed
- `SingerCreate` accepts optional `band_id`; all list/create endpoints are
  band-scoped. Non-existent nested ids now return 404 (was 422 in one case).

---

## [Stage 0] — Foundation & Architecture — 2026-08-31

Initial skeleton. No AI models — mock providers only.

### Added
- FastAPI backend with CRUD for singers, projects, songs, sections, lyric lines,
  and jobs; `/health` and OpenAPI docs at `/docs`.
- SQLAlchemy 2.0 ORM + Alembic migration for all core entities: Singer, Project,
  Song, SongSection, LyricLine, VocalRole, VocalAssignment, BandReference,
  GenerationJob, AudioAsset.
- `LyricLine` entity and section/line vocal-role resolution
  (`sr/common/resolver.py`) — the per-line singer-assignment amendment.
- Job system: `JobQueue` abstraction with `eager` / `inline` / `rq` backends,
  shared `run_job` runner capturing seed, params, provider version, input asset
  ids, logs, error, attempts, timing, and output assets with lineage.
- Provider ABCs (music / voice / stem / analysis / mastering / transcription),
  mock implementations that emit real silent WAVs, and a config-driven registry.
- `sr/common/allocation.py` — deterministic largest-remainder allocation +
  percentage normalization (70/20/10 @ 10 → 7/2/1).
- `sr/common/seeds.py` — blake2b child-seed derivation + bounded jitter.
- `sr/common/storage.py` — local filesystem store with an S3-shaped interface.
- `sr/orchestrator/pipeline.py` — generation stage graph + dry-run planner.
- Next.js app: home/health, singers, songs, jobs pages talking to the API.
- Scripts: `setup.ps1`, `dev.ps1`, `worker.ps1`, `test.ps1`, `stage_gate.py`.
- Optional `docker-compose.yml` (Postgres + Redis + api + worker + web).
- Docs: README, ARCHITECTURE, ROADMAP, MODEL_SETUP, DATASET_GUIDE, TEST_PLAN,
  DECISIONS, CHANGELOG.
- 29 automated tests (ruff clean).

### Stage 0 exit criteria — all PASS
- Stack boots locally · CRUD for singers/projects/songs · mock generation job
  queued → completed with lineage · test suite passes.
