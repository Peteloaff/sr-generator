# Architecture Decision Records

## ADR-0001 — SQLite default, Postgres-compatible code (Stage 0)

**Context.** Target machine is native Windows with no Docker, Postgres, or Redis.
The blueprint names PostgreSQL.

**Decision.** Use SQLAlchemy 2.0 + Alembic with portable column types. Default
`SR_DATABASE_URL` is SQLite (`storage/dev.db`); switching to Postgres is a URL
change only. Alembic uses `render_as_batch=True` so migrations work on SQLite.

**Consequences.** Zero-install local dev. Postgres-specific features (native
`JSONB` operators, partial indexes) are avoided until a stage needs them and
Postgres is provisioned. CI/prod set the Postgres URL.

---

## ADR-0002 — One package now, split into services later

**Context.** Blueprint lists `services/{api,orchestrator,music_provider,...}` as
separate services.

**Decision.** Stage 0 ships one Python package `sr/` with submodules mirroring
those responsibilities. Split into deployable services when a concrete driver
appears: a GPU worker at Stage 3, a music-provider service at Stage 7.

**Consequences.** Faster iteration and one test suite early. The provider ABCs
and the job queue are the seams along which services will separate, so the split
is mechanical, not a redesign.

---

## ADR-0003 — Redis-free job queue by default

**Context.** RQ needs Redis; Redis has no first-class native Windows build, and
RQ needs `SimpleWorker` on Windows (no `os.fork`).

**Decision.** `JobQueue` interface with three backends: `eager` (synchronous,
for tests), `inline` (background `ThreadPoolExecutor` in the API process, the
Stage 0 native default), and `rq` (Redis + `SimpleWorker`, the blueprint
target). `run_job(job_id)` is shared by all three.

**Consequences.** Local dev and the whole test suite run with no broker. Moving
to `rq` is an env var plus `scripts/worker.ps1`. The `inline` backend is
single-process and not for production scale — that's what `rq` is for.

---

## ADR-0004 — LyricLine + section/line vocal-role resolution

**Context.** The blueprint assigns vocals per **section**. The product owner
wants a per-line control: at the end of each lyric line, a dropdown of who sings
it (or weighted percentages for multiple singers).

**Decision.** Add a `LyricLine` entity. A `VocalRole` attaches to exactly one
parent — a `SongSection` (default) **or** a `LyricLine` (override), enforced by a
DB check constraint. `sr/common/resolver.py` resolves a line's effective roles:
line roles fully override; otherwise inherit the section's.

**Consequences.** Per-line control without losing bulk section edits. Slightly
more resolution logic in rendering. Percentages still normalize to 100 per role
regardless of parent.

---

## ADR-0005 — Deterministic allocation and seeds are library code, tested from Stage 0

**Context.** Blueprint acceptance tests 18–19 hinge on 70/20/10 → 7/2/1 and on
"same inputs + provider version + seed → same result".

**Decision.** `sr/common/allocation.py` (largest-remainder, stable tie-break) and
`sr/common/seeds.py` (blake2b child-seed derivation, bounded jitter) are pure
functions with unit tests now, even though heavy use starts at Stage 2.

**Consequences.** The math is locked and regression-guarded before any audio
code depends on it.

---

## ADR-0006 — Mock providers emit real (silent) WAV files

**Context.** Stage 0 must prove the job → asset → lineage → export path without
any model.

**Decision.** Mock providers write actual `.wav` files (silence) sized from the
requested duration, at deterministic paths derived from the seed.

**Consequences.** Storage, asset rows, duration/sample-rate metadata, and
download paths are all exercised for real. Swapping in a model provider changes
bytes, not plumbing.

---

## ADR-0007 — `Band` as the top-level tenant (Stage 1)

**Context.** The blueprint is "an AI version of one band". The product owner
wants to reuse the app for a second band if it works well - and retrofitting
tenancy onto a mature schema is painful.

**Decision.** Add a `Band` entity now, while the schema is young. `Singer`,
`Project`, `Song`, and `BandReference` all carry `band_id` (cascade delete). A
default band is auto-created on first run. The API resolves the active band from
`?band_id=`, an `X-Band-Id` header, or the default; the web app keeps the choice
in `localStorage` and sends the header. Singer names are unique *per band*, not
globally.

**Consequences.** Single-band UX is unchanged (one band, everything filtered).
A second band is one `POST /bands` away, fully isolated. Every list/create
endpoint now goes through the band dependency. Cross-band references (e.g. a
vocal assignment pointing at another band's singer) are rejected at the API.

---

## ADR-0008 — Squash migrations before the first release

**Context.** Stage 1 changed `singers` (drop global-unique `name`, add composite
unique + `band_id`). Alembic batch mode on SQLite does not reliably drop an
unnamed unique constraint, and there is no deployed database with real data.

**Decision.** Collapse the Stage 0 + Stage 1 migrations into a single
`initial schema (through stage 1)` revision. Do this only while nothing is
deployed; once real data exists, migrations are append-only.

**Consequences.** Clean schema, no batch-mode constraint gymnastics. Migration
history restarts from one revision.

---

## ADR-0009 — Bundled ffmpeg via `imageio-ffmpeg`

**Context.** Audio decode/probe/waveform needs ffmpeg. The target machine has no
ffmpeg on PATH and no Docker.

**Decision.** Depend on `imageio-ffmpeg`, which ships a static ffmpeg binary per
platform. `sr/common/audio.py` calls `imageio_ffmpeg.get_ffmpeg_exe()`. All
uploads are transcoded to a canonical 16-bit 44.1k WAV for analysis; the
original file is kept alongside.

**Consequences.** `pip install` is the only setup step for audio. A
system-installed ffmpeg can be preferred later via config if needed (e.g. for
hardware codecs). ffprobe is not bundled, so probing parses `ffmpeg -i` output.

---

## ADR-0010 — Stage 2 DSP is pure NumPy with deliberate approximations

**Context.** The layering engine needs gain, pan, timing offset, pitch shift, and
formant shift. Real pitch/formant shifting needs a phase vocoder or rubberband
(not in the bundled ffmpeg, adds heavy deps).

**Decision.** Implement DSP in pure NumPy for full determinism. Pitch shift is
resample-based (so it also shifts formants and is slightly lo-fi); formant shift
is a first-difference spectral tilt. Gain, pan (equal-power), timing offset, and
mixing are exact.

**Consequences.** The whole layering pipeline — allocation, humanization, stems,
mix, master, reproducibility — is proven now. A `PitchProvider` / real
time-stretch drops in later behind the same `TakeSpec` interface without touching
the engine. Documented as a limitation in ARCHITECTURE.md.

---

## ADR-0011 — Seeds masked to 63 bits

**Context.** `derive_seed` returned a full 64-bit value; stored as
`RenderTake.child_seed` it overflowed SQLite's signed-64-bit INTEGER, and NumPy's
`default_rng` wants a non-negative seed.

**Decision.** Mask `derive_seed` output to 63 bits (`(1<<63)-1`). Determinism
properties are unchanged (same input → same seed, different input → different).

**Consequences.** Seeds fit signed BIGINT (SQLite + Postgres), `np.int64`, and
`np.random.Generator` everywhere, with no per-call masking.

---

## ADR-0012 — Three-transaction job lifecycle

**Context.** A render creates many rows in one transaction. If a flush fails
partway, the session is poisoned — the old single-transaction runner could not
then record the failure (it tried to write to the rolled-back session).

**Decision.** `run_job` uses three transactions: (1) mark running + `attempts++`
and commit; (2) run the handler and persist results; (3) on any exception, a
fresh transaction marks the job failed with the error and traceback.

**Consequences.** A failed render leaves no partial assets (transaction 2 rolls
back) but still records its attempt count, status, and error. The job is visibly
`running` while it works.
