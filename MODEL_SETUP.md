# Model / Provider Setup

Stages 0–1 ship **mock providers only**. This file will grow as real adapters
land. The contract every provider implements is in `sr/providers/base.py`.

**ffmpeg** is already handled: `imageio-ffmpeg` (a base dependency) ships a static
binary, used by `sr/common/audio.py` for upload transcoding and waveforms. No
system install needed. ffprobe is not bundled — probing parses `ffmpeg -i`.

## Provider kinds

| Kind | ABC | Selected by | Real adapter arrives |
|---|---|---|---|
| music | `MusicGenerationProvider` | `SR_MUSIC_PROVIDER` | Stage 7 |
| voice | `VoiceProvider` | `SR_VOICE_PROVIDER` | Stage 3 |
| stem | `StemSeparationProvider` | `SR_STEM_PROVIDER` | Stage 5 |
| analysis | `AudioAnalysisProvider` | `SR_ANALYSIS_PROVIDER` | Stage 1/6 |
| mastering | `MasteringProvider` | `SR_MASTERING_PROVIDER` | Stage 4/8 |
| transcription | `TranscriptionProvider` | `SR_TRANSCRIPTION_PROVIDER` | Stage 3/8 |

All default to `mock`. Register a new implementation in
`sr/providers/registry.py`:

```python
register("voice", "rvc", MyRvcVoiceProvider)
```

then set `SR_VOICE_PROVIDER=rvc`. No call sites change.

## Research targets (not commitments)

- **Music generation:** ACE-Step 1.5-class open model with reference conditioning
  and adapter/LoRA support. MusicGen/AudioCraft and successors evaluated through
  the same `MusicGenerationProvider` contract.
- **Singing voice:** an authorized voice-conversion/synthesis stack that
  preserves melody, timing, lyrics, and expression controls per singer.
- **Stem separation:** a Demucs-class separator.

Every selection is an *implementation provider*, never a permanent product
dependency.

## GPU execution

When real models land, GPU work runs in a **separate worker process**
(`SR_QUEUE_BACKEND=rq` + `scripts/worker.ps1`), never in the API process, so the
UI/API stay responsive. Local or remote GPU workers both attach to the same
Redis queue.

## Postgres / Redis for parity (optional today)

Native Windows:

- **Redis:** install [Memurai](https://www.memurai.com/) (Redis-compatible) or
  run Redis under WSL2. Then `SR_QUEUE_BACKEND=rq`, `SR_REDIS_URL=redis://localhost:6379/0`.
- **Postgres:** install PostgreSQL 16, create `sr_generator`, then
  `SR_DATABASE_URL=postgresql+psycopg://USER:PASS@localhost:5432/sr_generator`
  and `pip install psycopg[binary]`.

Or just use `docker compose up` (see `docker-compose.yml`).
