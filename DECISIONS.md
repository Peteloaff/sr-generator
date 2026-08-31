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
