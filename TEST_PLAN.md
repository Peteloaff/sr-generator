# Test Plan

`scripts/test.ps1` runs ruff + pytest. `scripts/stage_gate.py <N>` checks a
stage's exit criteria and prints PASS/FAIL.

## Stage 0 — automated (29 tests, all passing)

| Area | File | Covers |
|---|---|---|
| Health / boot | `tests/test_health.py` | app boots, DB reachable, mock providers + job types registered |
| CRUD | `tests/test_crud.py` | singer create/read/update/delete, name uniqueness, **many singers**, project→song cascade, consent defaults false |
| Structure | `tests/test_sections_and_lines.py` | sections + lyric lines; line-belongs-to-song validation; **resolver: line overrides section, else inherit, else none** |
| Allocation | `tests/test_allocation.py` | normalize to 100; **70/20/10 @ 10 → 7/2/1**; sums to ensemble size for many sizes; deterministic + stable tie-break; `as_takes` order; child-seed stability/distinctness; bounded jitter range |
| Job pipeline | `tests/test_job_pipeline.py` | mock job queued→succeeded with asset + lineage; get/wait endpoints; **seed determinism** (same seed → same output path); failed job is safe + retryable, attempts increment |
| Migrations | `tests/test_migrations.py` | `alembic upgrade head` builds every model table from scratch |

## Blueprint acceptance tests (§18) — status

| # | Test | Stage | Status |
|---|---|---|---|
| 1 | Percentage normalization totals 100 / predictable rounding | 0 | ✅ `normalize_weights` |
| 2 | Ensemble allocator 70/20/10 @ 10 → 7/2/1; largest-remainder otherwise | 0 | ✅ `largest_remainder_allocation` |
| 3 | Seed determinism → same orchestration + humanization | 0 (seeds) / 2 (full) | ✅ seeds; ⬜ full pipeline |
| 4 | Section isolation — regen Chorus 1 leaves Verse 1 assets | 9 | ⬜ |
| 5 | Stem preservation — every render outputs stems + master | 2 | ⬜ |
| 6 | Voice isolation — singers independently selectable; disabling one doesn't corrupt others | 3 | ⬜ (model exists: independent `Singer` rows, cascade-scoped) |
| 7 | Consent enforcement — render fails safely when a flag is missing | 3 | ⬜ (flags + defaults in place) |
| 8 | Job recovery — failed GPU task retried without DB corruption | 0 | ✅ `test_failed_job_is_safe_and_retryable` |
| 9 | Asset lineage — every output knows its source assets + job | 0 | ✅ `generation_job_id` + `parent_asset_id` asserted |
| 10 | UI state fidelity — save/reload preserves boundaries, weights, roles, seeds, gains, pans, provider settings | 1 | ⬜ |

## Audio evaluation protocol (Stages 3–4, to be filled in)

- Fixed guide-phrase test set per singer.
- Metrics: intelligibility (subjective 1–5), alignment error (ms), pitch error
  (cents), repeatability (byte/spectral diff across identical seeds), stem
  bleed/phase.
- A/B: gain-only mix vs ensemble mode — panel scoring, phase-correlation check.
- Gate: agreed thresholds must pass before the stage is marked complete.
