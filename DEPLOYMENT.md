# AERON — Deployment Guide

Complete instructions for publishing AERON to GitHub, Vercel (frontend) and Render (backend) on free tiers.

> **No public deployment has been performed or verified.** The configuration in this repository is deployment-ready, but every URL below is a placeholder that only you can create. Free-tier limits were checked against the platforms' documentation in October 2026 and can change — re-check before relying on them.

---

## 0. Deployment topology

```
Browser
  │
  ├── https://<your-project>.vercel.app        ← React static build (Vercel Hobby)
  │        │
  │        └── fetch() with VITE_API_BASE_URL
  │
  └── https://<your-service>.onrender.com      ← FastAPI (Render free web service)
           │
           └── HTTPS → https://data.elexon.co.uk/bmrs/api/v1
```

The two services are independent. Each has its own root directory inside the same repository, which is the simplest way to keep one source of truth for both halves of the application.

---

## 1. Publish the source to GitHub

### 1.1 Create the repository

Use an **anonymous, descriptive repository name** — no company name, no personal name. Suggested names:

```
wind-forecast-intelligence
aeron-wind-analytics
gb-wind-forecast-lab
```

On <https://github.com/new>:

- **Repository name**: `wind-forecast-intelligence`
- **Description**: `AERON — historical evaluation of Elexon wind generation forecasts at a configurable decision cutoff`
- **Visibility**: Public (required for free Vercel Hobby and Render deployments from a public repo; both also support private repositories, but public keeps the free path simplest)
- **Initialise with**: leave all checkboxes (README, .gitignore, licence) **unchecked** — the project already contains its own.

### 1.2 Push from your machine

From the extracted project folder in PowerShell:

```powershell
cd C:\Projects\AERON_Wind_Forecast_Intelligence

git init
git add .
git commit -m "AERON wind forecast intelligence: historical forecast evaluation platform"

git branch -M main
git remote add origin https://github.com/<your-github-username>/wind-forecast-intelligence.git
git push -u origin main
```

### 1.3 Confirm nothing sensitive was committed

```powershell
git ls-files | Select-String -Pattern "\.env$|node_modules|\.cache|__pycache__"
```

This must print **nothing**. If it prints `.env` files, remove them:

```powershell
git rm --cached backend/.env frontend/.env
git commit -m "Remove local environment files from version control"
git push
```

`.gitignore` already excludes `node_modules/`, `dist/`, `.env`, `.env.*`, `__pycache__/`, `.venv/`, `backend/.cache/`. Only the `.env.example` templates are tracked.

---

## 2. Deploy the backend to Render

### 2.1 Create the service

1. Sign in at <https://render.com> with GitHub.
2. **New +** → **Web Service**.
3. Connect the `wind-forecast-intelligence` repository.
4. Configure:

| Setting | Value |
| --- | --- |
| Name | `aeron-api` |
| Region | Frankfurt (closest to Elexon and to UK users) |
| Branch | `main` |
| **Root Directory** | `backend` |
| Runtime | `Python 3` |
| **Build Command** | `pip install --no-cache-dir -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |
| Health Check Path | `/health` |

5. Add the environment variables listed in §2.2.
6. **Create Web Service**.

`render.yaml` in the repository root encodes the same configuration, so you can alternatively use **New +** → **Blueprint** and let Render read it. If you use the Blueprint, set the `CORS_ORIGINS` value yourself (it is marked `sync: false` so it is not committed).

### 2.2 Backend environment variables

| Key | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.12.7` |
| `DATA_MODE` | `live` |
| `ANALYSIS_START_DATE` | `2026-01-01` |
| `ANALYSIS_END_DATE` | `2026-01-31` |
| `DEFAULT_LEAD_HOURS` | `12` |
| `ALLOWED_LEAD_HOURS` | `4,8,12,24,36,48` |
| `CACHE_ENABLED` | `true` |
| `CACHE_DIR` | `/tmp/aeron-cache` |
| `CACHE_TTL_HOURS` | `24` |
| `LOG_LEVEL` | `INFO` |
| `CORS_ORIGIN_REGEX` | `https://([a-z0-9-]+\.)*vercel\.app` |
| `CORS_ORIGINS` | `https://<your-project>.vercel.app` |

`CACHE_DIR` must point somewhere writable. Render's free filesystem is ephemeral — the application handles that by design: after a restart the first request re-downloads January 2026 (a few seconds) and re-populates the cache.

If you have not deployed the frontend yet, set `CORS_ORIGINS` to a placeholder such as `http://localhost:5173` and update it after step 3.

### 2.3 Verify the backend

```powershell
curl.exe https://<your-service>.onrender.com/health
```

Expected:

```json
{"status":"ok","data_mode":"live","dataset_loaded":false,"cache_status":null,"retrieval_timestamp_utc":null,"analysis_start_date":"2026-01-01","analysis_end_date":"2026-01-31","version":"1.0.0"}
```

`dataset_loaded:false` is correct before the first data request. Now force a retrieval:

```powershell
curl.exe "https://<your-service>.onrender.com/api/overview?delivery_date=2026-01-15&lead_hours=12"
```

This first call downloads ~24,000 Elexon records and may take 5–15 seconds. A healthy response contains `"data_mode":"live"`, `"metrics"` and `"quality"`.

Also open <https://<your-service>.onrender.com/docs> to confirm the OpenAPI documentation renders.

### 2.4 Free-tier behaviour to expect

- The service **spins down after 15 minutes without inbound traffic**.
- The next request wakes it in **about one minute**; the browser may show the network error with a working **Retry** button.
- **750 free instance hours per workspace per month**; a spun-down service consumes none.
- **512 MB RAM, 0.1 CPU**, single instance, no persistent disk, no shell access.
- Local files are lost on every restart, redeploy or spin-down.

---

## 3. Deploy the frontend to Vercel

### 3.1 Create the project

1. Sign in at <https://vercel.com> with GitHub.
2. **Add New…** → **Project** → import `wind-forecast-intelligence`.
3. Configure:

| Setting | Value |
| --- | --- |
| Project Name | `aeron-wind-forecast-intelligence` |
| Framework Preset | **Vite** (auto-detected) |
| **Root Directory** | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Install Command | `npm ci` |
| Node.js Version | 20.x |

`frontend/vercel.json` already declares the framework, build command, install command, output directory and the SPA rewrite to `index.html` for client-side routing, so Vercel should pre-fill these.

### 3.2 Frontend environment variable

Add **before** the first deploy, for the **Production** environment (and Preview if you want preview builds to work):

| Key | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `https://<your-service>.onrender.com` |

Important properties of this variable:

- It is **inlined at build time**. Changing it requires a **redeploy**, not just a save.
- It is **public** — it appears in the browser bundle. Only the backend base URL belongs here; never a secret.
- Do not hardcode `localhost`; production must point at your deployed backend.

4. Click **Deploy**.

### 3.3 Close the CORS loop

After the frontend URL exists, copy it and return to Render → `aeron-api` → **Environment**:

```
CORS_ORIGINS = https://<your-project>.vercel.app
```

Save; Render redeploys automatically. The `CORS_ORIGIN_REGEX` value already allows any `*.vercel.app` preview deployment.

### 3.4 Verify the deployment

1. Open `https://<your-project>.vercel.app`.
2. The status bar should show `LIVE ELEXON DATA`, `API ONLINE`, and a retrieval timestamp.
3. If the very first load hits a sleeping Render instance, you will see a structured error with a **Retry** button — press it after the service wakes.
4. Open **Data Provenance** and confirm the record counts (1,488 actual, ~22,776 forecast) and the retrieval timestamp are present.
5. Download a CSV from **Forecast Explorer** to confirm the export path works through CORS (the `Content-Disposition` header is explicitly exposed).

---

## 4. Alternative free backends

Render is the documented path, but the backend is a standard ASGI application and runs on any Python 3.11+ host.

| Platform | Free tier | Start command | Notes |
| --- | --- | --- | --- |
| **Render** | Free web service, 512 MB, sleeps after 15 min | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | Documented above |
| **Railway** | Trial credit, then paid | same as above | Root directory `backend`, `$PORT` respected |
| **Fly.io** | Limited free allowance | `uvicorn app.main:app --host 0.0.0.0 --port 8080` | Requires a Dockerfile-based deploy; the provided backend Dockerfile works |
| **Hugging Face Spaces** | Free CPU Space | Docker Space using `backend/Dockerfile` | Works but less conventional for an API |
| **Koyeb** | Free instance | same as above | Sleeps on the free plan |

Whichever you choose, the same three things matter: the `$PORT` environment variable must be honoured, `CORS_ORIGINS` must contain the deployed frontend origin, and `CACHE_DIR` must be writable (ephemeral is fine).

---

## 5. Diagnosing common deployment errors

| Symptom | Cause | Fix |
| --- | --- | --- |
| Frontend shows "The AERON backend could not be reached" | `VITE_API_BASE_URL` missing or wrong at build time, or the Render service is asleep | Check the Vercel variable, then **Redeploy** Vercel. Wake the backend first, then retry |
| Browser console: `blocked by CORS policy` | Frontend origin not in `CORS_ORIGINS` | Add the exact origin (`https://…vercel.app`, scheme included, no trailing slash) in Render and redeploy |
| Render build fails: `No module named app` | Root Directory not set to `backend` | Set **Root Directory** = `backend` |
| Render build fails on `uvicorn` | Start command run from the wrong directory | Start command must be `uvicorn app.main:app --host 0.0.0.0 --port $PORT` with `rootDir: backend` |
| Render deploy shows live but returns 502 | Start command crashed on boot | Open **Logs**; usually a missing environment variable or an unquoted `$PORT` |
| `Elexon rejected the request` (502) | A date window exceeded 7 days, or a malformed parameter | Do not edit `ELEXON_MAX_CHUNK_DAYS` above 7 |
| `Elexon API did not respond successfully after retries` (503) | Upstream outage or timeout | Retry; raise `ELEXON_TIMEOUT_SECONDS` if consistently slow |
| All metrics `null`, coverage 0% | No eligible publication before the cutoff, or actuals missing | Loosen the cutoff (`T − 24 h` or `T − 48 h`), check the Provenance warnings |
| Vercel 404 on `/accuracy` after refresh | SPA rewrite missing | Confirm `frontend/vercel.json` is present and Root Directory is `frontend` |
| Vercel build fails: `npm ci` cannot find a lockfile | `package-lock.json` not committed | Commit `frontend/package-lock.json` |
| Blank white page in production | Build-time variable missing, or an asset path failure | Check the browser console; redeploy after fixing environment variables |
| First request takes ~60 s | Render free instance was asleep | Expected; use a keep-alive ping if the demonstration needs instant responses |
| Data disappears after idle period | Ephemeral filesystem cleared the cache | Expected; the first request re-downloads and re-caches |

Useful log commands:

```powershell
# Render: Dashboard → service → Logs (live stream)

# Vercel: Dashboard → project → Deployments → select deployment → Build Logs / Runtime Logs
```

---

## 6. Deployment checklist

- [ ] Repository pushed to GitHub with an anonymous name
- [ ] `git ls-files` shows no `.env`, `node_modules`, `.cache` or `__pycache__`
- [ ] Render service created with **Root Directory** = `backend`
- [ ] Render environment variables set, including `CACHE_DIR=/tmp/aeron-cache`
- [ ] `https://<service>.onrender.com/health` returns `status: ok`
- [ ] `/api/overview?delivery_date=2026-01-15&lead_hours=12` returns real metrics
- [ ] Vercel project created with **Root Directory** = `frontend`
- [ ] `VITE_API_BASE_URL` set to the Render URL and a fresh deploy triggered
- [ ] `CORS_ORIGINS` on Render contains the exact Vercel origin
- [ ] Frontend status bar shows `API ONLINE` and `LIVE ELEXON DATA`
- [ ] CSV export downloads successfully from the deployed frontend
- [ ] Provenance page shows real record counts and a retrieval timestamp
