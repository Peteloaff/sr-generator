# Deploying SR Generator

Target architecture (Phase 1 — "make it reachable from any device"):

| Piece | Service | Notes |
|---|---|---|
| Web app (Next.js) | **Vercel** | auto-builds from GitHub; one env var |
| API (FastAPI) | **Google Cloud Run** | container from this repo's `Dockerfile` |
| Database | **Supabase Postgres** | app is Postgres-native (`SR_DATABASE_URL`) |
| Audio files | **Supabase Storage** (S3 API) | `SR_STORAGE_BACKEND=s3` |
| Jobs | in-process (inline) | Cloud Run request runs the render; no separate worker for MVP |

Still **single-tenant** after Phase 1 — one shared band workspace, no login. Auth,
per-user isolation, and billing are Phase 3 (see the bottom of this file).

---

## 0. Prerequisites (once)

- `gcloud` CLI installed and `gcloud auth login`
- A Google Cloud project with **billing enabled**
- A Supabase project
- The Vercel CLI (`npm i -g vercel`) or just the Vercel dashboard
- This repo pushed to GitHub

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
```

---

## 1. Supabase — database + storage bucket

**Database.** Supabase → Project Settings → Database → *Connection string* →
**Session pooler** (works with a long-lived container). It looks like:

```
postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

The app needs the `psycopg` driver prefix:

```
SR_DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

**Storage.** Supabase → Storage → **New bucket** named `sr-audio` (keep it
**private**). Then Storage → *Settings* → **S3 connection**: enable it and create
**S3 access keys**. You get:

```
endpoint:  https://<ref>.supabase.co/storage/v1/s3
region:    <your project region, e.g. us-east-1>
access key id / secret access key
```

---

## 2. API → Google Cloud Run

Easiest with **Cloud Shell** (console.cloud.google.com → terminal icon, top
right) — `gcloud` is installed and already logged in. Or install `gcloud`
locally and `gcloud auth login`.

```bash
# --- one-time setup --------------------------------------------------
PROJECT_ID=your-gcp-project-id     # <- yours
REGION=us-central1

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com

# --- secrets (paste the real values from Supabase, step 1) ----------
printf '%s' 'postgresql+psycopg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require' \
  | gcloud secrets create SR_DATABASE_URL --data-file=-
printf '%s' '<supabase s3 secret access key>' \
  | gcloud secrets create SR_S3_SECRET_ACCESS_KEY --data-file=-

# let Cloud Run read them
PN=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
for S in SR_DATABASE_URL SR_S3_SECRET_ACCESS_KEY; do
  gcloud secrets add-iam-policy-binding "$S" \
    --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done

# --- get the code onto Cloud Shell, then deploy from source ---------
git clone https://github.com/Peteloaff/sr-generator.git
cd sr-generator

gcloud run deploy sr-generator-api \
  --source . --region "$REGION" --allow-unauthenticated \
  --memory 2Gi --cpu 2 --timeout 900 --concurrency 4 --max-instances 3 \
  --set-secrets SR_DATABASE_URL=SR_DATABASE_URL:latest,SR_S3_SECRET_ACCESS_KEY=SR_S3_SECRET_ACCESS_KEY:latest \
  --set-env-vars '^@^SR_STORAGE_BACKEND=s3@SR_S3_ENDPOINT_URL=https://<ref>.supabase.co/storage/v1/s3@SR_S3_REGION=us-east-1@SR_S3_BUCKET=sr-audio@SR_S3_ACCESS_KEY_ID=<supabase s3 access key id>@SR_QUEUE_BACKEND=inline@SR_API_CORS_ORIGINS=*'
```

`--source .` uploads the repo, builds the `Dockerfile` on Cloud Build (creates an
Artifact Registry repo automatically the first time — say yes), and deploys.
`^@^` makes `@` the list separator so the URLs' `,` and `:` don't split it.
Start with `SR_API_CORS_ORIGINS=*` and lock it to the Vercel URL after step 3.

The container runs `alembic upgrade head` on start, so this first deploy creates
the schema in Supabase. If the deploy shows the revision failing to start, check:

```bash
gcloud run services logs read sr-generator-api --region "$REGION" --limit 50
```

Get the URL and smoke-test:

```bash
URL=$(gcloud run services describe sr-generator-api --region "$REGION" --format='value(status.url)')
curl "$URL/health"
```

Later redeploys: `git pull && gcloud run deploy sr-generator-api --source . --region "$REGION"`
(env/secrets stick). `cloudbuild.yaml` is there if you want deploy-on-push CI.

---

## 3. Web app → Vercel

Vercel → **Add New Project** → import the GitHub repo.

- **Root Directory:** `apps/web`
- **Framework preset:** Next.js (auto)
- **Environment Variable:** `NEXT_PUBLIC_API_BASE = https://sr-generator-api-xxxx-uc.a.run.app`

Deploy. Then go back to Cloud Run and set `SR_API_CORS_ORIGINS` to the real
Vercel URL (step 2) if you guessed it earlier.

Custom domain: add it in Vercel, then add it to `SR_API_CORS_ORIGINS` too
(comma-separated).

---

## 4. Redeploys

- **Web:** push to `main` → Vercel auto-builds.
- **API:** `gcloud builds submit --config cloudbuild.yaml` (or connect the repo
  in the Cloud Build console for deploy-on-push).

---

## Notes / limits (MVP)

- **Scratch disk.** With `SR_STORAGE_BACKEND=s3` the container downloads/creates
  WAVs in `/tmp/sr-work` (in-memory on Cloud Run) before uploading. A full-song
  generation is ~50–150 MB of scratch; `--memory=2Gi` covers it. Instances
  recycle, clearing scratch. If you see OOMs, raise memory or lower concurrency.
- **Cold starts.** `--max-instances=3`, scale-to-zero. First request after idle
  takes a few seconds. Set `--min-instances=1` to avoid it (costs ~$/month).
- **Cost driver.** Audio rendering is CPU-bound; you pay vCPU-seconds while a
  request runs. Keep `--concurrency` low so one slow render doesn't starve others.
- **Voice consent.** The app already gates training/generation on per-singer
  consent flags. A public/commercial deployment should also put voice-likeness
  terms in front of users — get legal review before selling.

---

## Phase 3 — turning it into a sellable SaaS (not built yet)

1. **Auth** — Supabase Auth. Add a `User`/`Org` entity; scope every `Band`
   (and therefore Song/Singer/Reference) to an org. Verify the Supabase JWT in a
   FastAPI dependency; replace the `X-Band-Id` header trust model.
2. **Billing** — Stripe. Plans + usage metering (generations, storage GB,
   render-minutes). Enforce quotas in the job-submission path.
3. **Hardening** — rate limits, request size caps, per-org storage prefixes,
   backups (Supabase point-in-time restore), an async worker (Cloud Tasks or a
   second Cloud Run service on `SR_QUEUE_BACKEND=rq`) so long renders don't hold
   an HTTP connection.
4. **Legal** — ToS/privacy, explicit voice-likeness authorization capture,
   DMCA/abuse process.
