# Changelog

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
