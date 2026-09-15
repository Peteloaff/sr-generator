# SR Generator — desktop build

A one-click local install: a single folder containing `SR Generator.exe` that
runs the **entire** stack on your PC — the FastAPI backend, the web UI, a SQLite
database, and local file storage. No Python, no Node, no Docker, no cloud bill.
It uses your machine's CPU and disk instead of Cloud Run + Supabase.

The cloud deployment at https://staticue.com is unaffected — same code, different
entry point. See [DEPLOY.md](DEPLOY.md) for that.

## Running it

1. Double-click `SR Generator.exe` (inside the `SR Generator` folder — keep the
   folder together).
2. A console window opens, migrations run, and your browser opens to
   `http://127.0.0.1:<port>`.
3. Closing the console window stops the app.

All data lives in `~/.sr-generator` (`C:\Users\<you>\.sr-generator`):

| Path | What |
|---|---|
| `sr.db` | the SQLite database (songs, singers, players, sections, jobs) |
| `storage/` | generated + uploaded audio |
| `pydeps/` | the separation engine (Demucs), installed on first use — see below |

Delete that folder for a clean slate. Back it up to keep your work.

### Learning a player's style (Demucs, first use only)

Per-instrument separation uses **Demucs** (PyTorch, ~2 GB). It is **not**
bundled — the first time you train a player, the app installs it into
`~/.sr-generator/pydeps` (needs a system Python 3.12+ on PATH and a network
connection). That one download takes a few minutes; every run after is instant.

If you don't have Python or want to skip it, set `SR_MULTISTEM_PROVIDER=bandsplit`
for the rough dependency-free split (fine for a quick pass, not for real tone
matching).

### Overrides (optional)

Environment variables, all honoured before defaults are applied:

| Var | Default | Purpose |
|---|---|---|
| `SR_HOME` | `~/.sr-generator` | data directory |
| `SR_PORT` | a free port | fix the port |
| `SR_DATABASE_URL` | `sqlite:///<SR_HOME>/sr.db` | point at Postgres instead |
| `SR_STORAGE_BACKEND` | `local` | `s3` to use Supabase Storage |

Instead of setting Windows environment variables by hand, drop a plain text
file at `<SR_HOME>/.env` (default `C:\Users\<you>\.sr-generator\.env`) — it's
read automatically on startup, before the defaults above are applied.

### Real music generation (optional)

By default the desktop app uses the same free, offline placeholder synth as
everything else (`local_synth` — deterministic but not real instruments).
To use a real hosted model instead, put this in your `.env`:

```
SR_MUSIC_PROVIDER=replicate
SR_REPLICATE_API_TOKEN=your-own-token-here
```

Get a token from [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
(free account, pay-per-second billing — set a spending cap in Replicate's
billing settings). **This is your own token and your own bill** — the
desktop app never ships or shares anyone else's credentials, so each person
running the `.exe` needs their own. See
[MODEL_SETUP.md](MODEL_SETUP.md#using-the-hosted-musicgen-model-replicate)
for details on the model itself.

## Building it

On a machine with **Python 3.12** and **Node 18+**:

```powershell
pip install -e ".[cloud,desktop]"
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
```

The script:

1. builds the web UI as a static export — `STATIC_EXPORT=1` and
   `NEXT_PUBLIC_API_BASE=/api` (so the bundled UI calls the bundled API on the
   same origin) → `apps/web/out/`;
2. freezes the backend with PyInstaller (`sr_generator.spec`), bundling
   `apps/web/out` as `web/`, the Alembic migrations, `ffmpeg` (imageio-ffmpeg),
   and `libsndfile` (soundfile);
3. leaves the result in `dist/SR Generator/`.

Ship that folder as-is, or wrap it in an installer (Inno Setup / NSIS).

## How it works

`sr/desktop.py` is the entry point. When `SR_FRONTEND_DIR` is set, `create_app()`
in [sr/api/main.py](sr/api/main.py) moves every API router under `/api` and
mounts the static export at `/` (`html=True`, so `/song` resolves to
`song/index.html` for the client-routed pages). In the cloud that variable is
unset, so the API keeps its bare paths and Vercel serves the frontend.

The only frontend change the export required: the old `/songs/[id]` dynamic
route became `/song?id=<id>` (a static page reading the id from the query
string) — dynamic routes can't be statically exported without a Node runtime.
