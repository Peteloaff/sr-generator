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
| `sr.db` | the SQLite database (songs, singers, sections, jobs) |
| `storage/` | generated + uploaded audio |

Delete that folder for a clean slate. Back it up to keep your work.

### Overrides (optional)

Environment variables, all honoured before defaults are applied:

| Var | Default | Purpose |
|---|---|---|
| `SR_HOME` | `~/.sr-generator` | data directory |
| `SR_PORT` | a free port | fix the port |
| `SR_DATABASE_URL` | `sqlite:///<SR_HOME>/sr.db` | point at Postgres instead |
| `SR_STORAGE_BACKEND` | `local` | `s3` to use Supabase Storage |

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
