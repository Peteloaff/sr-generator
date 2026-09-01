# Model / Provider Setup

**Voice** (`local_dsp`, Stage 3), **stem** (`center_split`, Stage 5), **analysis**
(`local_mir`, Stage 6) and **music** (`local_synth`, Stage 7) all have real
default providers — dependency-free stand-ins that exercise the full contract.
Mastering / transcription are still `mock`. The contract every provider
implements is in `sr/providers/base.py`.

**ffmpeg** is already handled: `imageio-ffmpeg` (a base dependency) ships a static
binary, used by `sr/common/audio.py` for upload transcoding and waveforms. No
system install needed. ffprobe is not bundled — probing parses `ffmpeg -i`.

## Provider kinds

| Kind | ABC | Selected by | Default | Real adapter |
|---|---|---|---|---|
| music | `MusicGenerationProvider` | `SR_MUSIC_PROVIDER` | **`local_synth`** | Stage 7 ✅ + generative model |
| voice | `VoiceProvider` | `SR_VOICE_PROVIDER` | **`local_dsp`** | Stage 3 ✅ + neural |
| stem | `StemSeparationProvider` | `SR_STEM_PROVIDER` | **`center_split`** | Stage 5 ✅ + Demucs |
| analysis | `AudioAnalysisProvider` | `SR_ANALYSIS_PROVIDER` | **`local_mir`** | Stage 6 ✅ + librosa/model |
| mastering | `MasteringProvider` | `SR_MASTERING_PROVIDER` | `mock` | Stage 4/8 |
| transcription | `TranscriptionProvider` | `SR_TRANSCRIPTION_PROVIDER` | `mock` | Stage 3/8 |

Register a new implementation in `sr/providers/registry.py`:

```python
register("voice", "rvc", MyRvcVoiceProvider)
```

then set `SR_VOICE_PROVIDER=rvc`. No call sites change.

## Voice providers (Stage 3)

| name | what it is | needs |
|---|---|---|
| `local_dsp` (default) | real guide→singer conversion in pure NumPy — pitch to register, STFT formant warp, spectral tilt, breath, drive. Words preserved, voice changed. | nothing |
| `mock` | fast deterministic detune only | nothing (used by fast tests) |
| `http` | POSTs to a GPU voice-model service | `SR_VOICE_HTTP_URL`, `httpx` |

**`VoiceProvider` contract** — a neural model implements exactly these two:

```python
def analyze(self, sample_paths: list[Path], *, singer_ref: str) -> dict
    # training samples -> a voice profile / model descriptor (stored on the Singer)

def convert(self, *, guide_path: Path, profile: dict, params: dict, seed: int) -> VoiceConversion
    # one guide vocal -> converted mono audio (VoiceConversion(samples, sample_rate, ...))
```

The `train_singer` job calls `analyze`; `render_section` calls `convert` (result
cached by `(provider version, guide hash, profile)`).

### Plugging in a neural model (RVC / so-vits-svc / DiffSinger)

**Option A — in-process** (a GPU worker box): implement `analyze`/`convert` in a
new `sr/providers/voice_<name>.py` (load weights lazily, keep them off the API
process), `register("voice", "<name>", ...)`, run the API/worker where the GPU is,
`SR_VOICE_PROVIDER=<name>`.

**Option B — remote service** (recommended): wrap the model in a small HTTP
service exposing `POST /analyze` (multipart `samples`, form `singer_ref` → JSON
profile) and `POST /convert` (multipart `guide`, form `profile` + `seed` → WAV
body, optional `X-Provider-Version` header). Then `SR_VOICE_PROVIDER=http`,
`SR_VOICE_HTTP_URL=http://gpu-box:8100`. `HttpVoiceProvider` is already written.

Either way the app, the Vocal Director, caching, consent, and the layering engine
are untouched — see `sr/providers/voice_http.py` for the wire format.

## Music providers (Stage 7)

| name | what it is | needs |
|---|---|---|
| `local_synth` (default) | deterministic NumPy instrumental engine (`sr/common/musicgen.py`) — drums quantised to the BPM, a diatonic progression in the key, bass/pad/arp/drone. Trains band adapters by distilling the Band DNA. Byte-reproducible from a seed. | nothing |
| `mock` | near-silent stereo noise | nothing (fast tests) |
| `http` | a real generative-music service | `SR_MUSIC_HTTP_URL`, `httpx` |

**`MusicGenerationProvider` contract** — a real model implements:

```python
def generate(self, *, prompt: str, params: dict, seed: int, adapter: dict | None) -> MusicGeneration
    # -> MusicGeneration(audio (n,2) float32, sample_rate, provider, provider_version, metadata)
    # params carries bpm / key / duration; adapter is a BandAdapter.spec_json (or None)

trains_adapter: bool = False
def train_adapter(self, *, manifest: dict, dna: dict, params: dict) -> BandAdapterSpec
    # the strict training manifest + band_dna -> a conditioning spec (opaque or explicit),
    # stored as a BandAdapter row with its dataset_version
```

`train_band_adapter` calls `train_adapter`; `generate_instrumental` calls
`generate` and wires the result in as the section's `instrumental_bed`.

### Plugging in a generative model (ACE-Step / MusicGen-class)

**Remote service** (recommended): `POST /generate` (JSON `{prompt, bpm, key,
seconds, seed, adapter}` → WAV body, optional `X-Provider-Version`) and, if it
supports adapters, `POST /train-adapter` (JSON `{manifest, dna, params}` → JSON
spec). Then `SR_MUSIC_PROVIDER=http`, `SR_MUSIC_HTTP_URL=http://gpu-box:8200`.
`HttpMusicProvider` is already written (`sr/providers/music_http.py`). The
adapter row, the jobs, the section-bed wiring and the web flow don't change; the
tempo-lock / determinism / lineage tests still apply to the model's output.

## Stem separation providers (Stage 5)

| name | what it is | needs |
|---|---|---|
| `center_split` (default) | mid/side soft-mask center-channel separation, pure NumPy | nothing |
| `mock` | trivial centre split (tests) | nothing |
| `http` | a Demucs/MDX-class service | `SR_STEM_HTTP_URL`, `httpx` |

**Contract**: `separate(source_path: Path, params) -> StemSeparation(stems={...}, sample_rate)`.
For `http`, the service takes `POST /separate` (multipart `audio`) and returns a
zip of named WAV stems (`vocals.wav`, `drums.wav`, …). Set
`SR_STEM_PROVIDER=http` + `SR_STEM_HTTP_URL`. The rest of the pipeline
(use-derived-stems, render, assemble) is unchanged regardless of stem count.

## Research targets (not commitments)

- **Music generation:** ACE-Step 1.5-class open model with reference conditioning
  and adapter/LoRA support, dropped in behind the Stage 7
  `MusicGenerationProvider` contract (currently `local_synth`). MusicGen/AudioCraft
  and successors evaluated the same way.
- **Singing voice:** RVC / so-vits-svc / DiffSinger-class, per authorized singer,
  behind the `analyze`/`convert` contract above.
- **Stem separation:** a Demucs-class separator.
- **Lyrics / guide melody (Stage 8):** the song planner writes a seeded lyric
  scaffold and a deterministic guide melody today; a language model and a
  melody/vocal model would slot in at `songplan` / `sr/common/guide.py` without
  changing the full-song job or the resulting project shape.
- **Vocal morph (Stage 11):** a real timbre-interpolation model implements the
  same preview + quality-score contract in `sr/services/morph.py`; it stays
  behind `SR_EXPERIMENTAL_MORPH` until its scores are reliably high.

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
