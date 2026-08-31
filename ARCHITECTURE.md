# Architecture

## Principles (enforced, not aspirational)

1. **One stage at a time.** No stage-N+1 code until stage-N automated tests and
   exit criteria pass. See [ROADMAP.md](ROADMAP.md).
2. **Providers are replaceable.** The app talks only to the ABCs in
   `sr/providers/base.py`. Swapping ACE-Step / RVC / anything must not touch code
   outside `sr/providers/`.
3. **Everything long-running is a job.** `GenerationJob` records seed, params,
   provider + version, input asset ids, logs, error, attempts, timing, outputs.
4. **Assets are versioned and have lineage.** Every `AudioAsset` knows its
   `generation_job_id` and `parent_asset_id`.
5. **Stems are first-class.** Never collapse to a master-only artifact.
6. **Allocation ≠ gain.** `weight_percent` (ensemble allocation), `gain_db` (mix
   level), and future timbre-blend are three separate concepts.
7. **Consent is enforced.** No training or rendering when a required Singer
   consent flag is false.

## Components

| Module | Responsibility | Stage it grows |
|---|---|---|
| `sr/api` | FastAPI HTTP surface, CRUD, job submission | 0 → |
| `sr/models` | SQLAlchemy ORM — the core data model | 0 → |
| `sr/providers` | provider ABCs + mock impls + registry | 0 (mock), 3+ (real) |
| `sr/worker` | queue backends, job runner, handlers | 0 → |
| `sr/orchestrator` | generation pipeline (stage graph) | 2 → |
| `sr/common` | allocation, seeds, storage, role resolver | 0 → |
| `apps/web` | Next.js UI (DAW-style timeline later) | 0 → |

> The blueprint lists these as separate `services/*`. In Stage 0 they are modules
> in one Python package; they split into independently deployable services when a
> real need appears (GPU worker at Stage 3, music provider at Stage 7). See
> [DECISIONS.md](DECISIONS.md) ADR-0002.

## Data model

```
Band 1─* Singer
Band 1─* BandReference           (Band DNA, Stage 6)
Band 1─* Project 1─* Song 1─* SongSection 1─* LyricLine
Band 1───────────* Song                │                │
                         └──────── VocalRole ───────────┘   (exactly one parent: section OR line)
                                       │
                                       *─ VocalAssignment ─* Singer
Song 1─* GenerationJob 1─* AudioAsset ─┐
AudioAsset *─1 AudioAsset (parent)  ────┘  (lineage)
```

### Band scoping (ADR-0007)

`Band` is the top-level tenant. `Singer`, `Project`, `Song`, and `BandReference`
carry `band_id` and cascade-delete with the band. A default band is auto-created
on first run. The active band is resolved by `sr/api/deps.get_band` from
`?band_id=`, the `X-Band-Id` header, or the default; the web app stores the
choice in `localStorage`. Singer names are unique per band. The API rejects
cross-band references (e.g. assigning another band's singer to a role). The
product stays single-band in feel — a second band is one `POST /bands`.

### LyricLine and role resolution (SR Generator amendment)

The blueprint assigns vocals at the section level. SR Generator adds
`LyricLine`, and a `VocalRole` may attach to a **section** (the default) or a
**single line** (an override).

**Resolution rule** (`sr/common/resolver.py`): if a line has its own vocal
roles, they fully override the section's. Otherwise the line inherits the
section's roles. This keeps "set the whole chorus in one action" working while
allowing per-line control. UI target: each lyric line shows a trailing chip with
the resolved singer(s) — `Pete` or `Brian 70 / Pete 30` — click to edit.

## Job flow

```
POST /jobs ──► GenerationJob(status=queued) ──► queue.enqueue(job_id)
                                                     │
        ┌────────────────────────────────────────────┤
        ▼ eager: run now      ▼ inline: thread pool   ▼ rq: Redis + SimpleWorker
                         run_job(job_id)
                              │
     status=running ─► handler(job) ─► provider call ─► AudioAsset rows (+lineage)
                              │
              status=succeeded / failed (safe, retryable)
```

Queue backend is chosen by `SR_QUEUE_BACKEND` (`eager` | `inline` | `rq`).
`inline` is the Stage 0 native default and needs no Redis; the API process runs
jobs in a background thread. `rq` matches the blueprint target and needs Redis
(or Memurai) plus `scripts/worker.ps1`.

## Generation pipeline (declared, mostly stubbed)

`sr/orchestrator/pipeline.py` fixes the stage order from blueprint §10:
plan → music → guide melody → vocal-direct → voice render → ensemble expand →
align → vocal process → stem mix → master → export. Each stage becomes one or
more `GenerationJob`s as later stages land. `plan_dry_run(song_id)` returns the
ordered steps a full generation *would* run.

## Audio pipeline (`sr/common/audio.py`)

ffmpeg comes from `imageio-ffmpeg` (bundled binary, no system install — ADR-0009).
On upload:

1. Original bytes stored at `references/{band}/{song}/original.{ext}`.
2. Transcoded to `canonical.wav` (16-bit / 44.1k) — the single format everything
   downstream reads.
3. `peaks.json` — downsampled `[min, max]` pairs for the waveform, cached beside
   the audio and regenerated on demand.

`AudioAsset(asset_type="upload")` holds the handle; canonical + peaks are
sidecars by convention. Stage 2 (layering) and Stage 5 (separation) build on the
canonical WAV.

## Vocal weight normalization (`sr/services/vocal.py`)

`weight_percent` is stored exactly as entered. `normalized_shares(role)` computes,
on read: the 100%-scaled split (`normalize_weights`) and — for ensemble roles
(background / gang / harmony) — the integer take allocation via
`largest_remainder_allocation`. Lead/double are always one take. The UI shows
`Brian 70 → 7 takes` without ever mutating the stored weights.

## Vocal-stack quality (Stage 4)

- **Harmony intervals** — `VocalAssignment.interval_semitones`; `plan_role_takes`
  adds `(interval + detune) * 100 + jitter` cents. Kept in `flat` mode.
- **Per-role processing** (`sr/common/vocalfx.py`) — `VocalRole.processing_json`
  is an ordered chain (`deesser` / `eq` / `compressor`) run on the summed role
  stem. Plus `stack_gain(n) = 1/√n` so a 12-take gang doesn't build up 12×.
- **A/B** — `render` takes `mode`: `ensemble` (full) or `flat` (naive: no
  humanisation / spread / stack-comp / chain — "the same take, N copies").
  `POST /sections/{id}/ab` renders both, then compares `width_ratio` (side/mid
  RMS), `stereo_correlation` (L vs R), `mono_compat` (mono-sum energy retained).
  Verdict `ensemble_clearly_different` = wider **and** less correlated **and** no
  phase collapse.
- **`VocalPreset`** (`sr/services/presets.py`) — captures roles with singers *by
  name*, so a stack recipe applies to any section of any band.

## Singing voice provider (Stage 3)

A guide vocal (one melody/phrase per section) is converted into each singer's
voice. The `VoiceProvider` contract (`sr/providers/base.py`):

| method | purpose |
|---|---|
| `analyze(sample_paths, singer_ref)` | derive a voice profile / model descriptor from training samples |
| `convert(guide_path, profile, params, seed)` | → `VoiceConversion` (raw mono audio) |

Implementations: **`local_dsp`** (default — `sr/common/voice.py`: pitch to the
singer's register, STFT formant warp, spectral tilt, breath, drive — the words
survive, the voice changes), **`mock`** (fast detune), **`http`** (POSTs to
`SR_VOICE_HTTP_URL` — a local or remote GPU model service). A neural model
(RVC / so-vits-svc / DiffSinger) implements the same two methods — see
`MODEL_SETUP.md`.

**Render resolution** per singer (`sr/services/render.py:_base_vocal`):
uploaded `source_take` → guide + `training_status=="ready"` voice model (converted,
cached) → deterministic placeholder.

**Consent** (`sr/services/consent.py`): a render is 403 if any assigned singer
lacks `consent_generation`; `train_singer` fails without `consent_training`.
Checked at the API and again inside the job.

**Conversion cache** (`sr/services/cache.py`): filesystem-first. A conversion is
a WAV at `cache/voice_conversion/{key}` keyed by `(provider version, guide hash,
profile)`, written before the render transaction commits — so a job retry after a
rollback finds the file and skips the work. The `RenderCache` row is best-effort
bookkeeping. (SQLite's single writer cannot grant a second concurrent write
transaction, so the cache cannot rely on one.)

## Audio layering engine (Stage 2)

Turns Vocal Director definitions into rendered audio, deterministically.

```
render_section job (one transaction)
  for each VocalRole:
    plan_role_takes(role, seed)                     # sr/services/layering.py
      largest-remainder allocation -> N TakeSpecs
      each TakeSpec: child_seed = derive_seed(seed, role, singer, k)
                     timing/pitch/formant/gain/pan = fixed offset + bounded jitter
                     pan also fans out across +/- role.width
    for each TakeSpec:
      source = uploaded source_take  OR  deterministic mock synth   # sr/common/synth.py
      DSP: pan -> time_offset -> pitch_shift -> formant_tilt -> gain # sr/common/dsp.py
      -> take_stem AudioAsset  + RenderTake row (stores every applied value)
    sum takes -> role_stem
  group role stems -> stem_lead_vocal / stem_background_vocal / stem_gang_vocal
  sum -> vocal_bus  (+ optional instrumental_bed) -> mix -> master
```

Every artifact is an `AudioAsset` with `parent_asset_id` + `generation_job_id`.
`RenderTake` rows make a render reproducible take-for-take. Same section config +
seed + sources + engine version → identical WAV bytes (verified by hashing the
master across re-renders).

DSP is pure NumPy for determinism. Pitch shift is resample-based (moves formants
too) and formant is a light spectral tilt — both are placeholders for a real
pitch/formant provider in a later stage (ADR-0010).

## Project export / import (`sr/services/project_io.py`)

`export_project` → self-contained JSON: project + songs + sections + lyric lines
+ vocal roles + assignments, with singers referenced **by name** (not id) so a
project is portable across bands. `import_project` rebuilds it under a target
band, creating placeholder singers (consent flags false) for any name not
already present. Round-trip is byte-identical (`export == re-export`).

## Storage

`sr/common/storage.py` — `LocalStorage` rooted at `SR_STORAGE_ROOT`, with an
S3-shaped interface (`write_bytes`, `read_bytes`, `copy_in`, `exists`,
`url_for`). An S3 backend implements the same surface later.

## Configuration

All config is env-driven with the `SR_` prefix (`.env` supported). See
`.env.example`. `sr/config.py` is the single source of truth.
