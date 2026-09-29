# ChargeWise – Beginner Deployment Guide

## Part A – Run locally
1. **Download** `ChargeWise.zip`. 2. **Extract** it. 3. **Open** the `ChargeWise` folder in VS Code (File → Open Folder).
4. **Install Python 3.10+** from python.org (tick "Add to PATH"). Check: `python --version`.
5. **Virtual environment** (VS Code terminal, in the ChargeWise folder):
   * Mac/Linux: `python3 -m venv .venv && source .venv/bin/activate`
   * Windows: `py -m venv .venv` then `.venv\Scripts\activate`
6. **Dependencies:** `pip install -r requirements.txt`
7. **Prepare dataset:** nothing needed for the demo (auto-generated, synthetic). For real data put your file at `data/raw/sessions.csv` and your coordinates in `data/station_locations.csv` (see README).
8. **Train:** `python train.py` then `python predict.py`
9. **Run backend:** `uvicorn backend.main:app --reload --port 8000` → open http://localhost:8000/api/health (should show `"status":"ok"`).
10. **Install Node.js** (LTS) from nodejs.org. Check `node -v`.
11. **Frontend dependencies** (new terminal): `cd frontend` then `npm install`
12. **Run frontend:** `npm run dev` → open http://localhost:5173
13. **Test locally:** map appears with 12 markers; click one; try modes, filters, Nearby, What-if.

## Part B – GitHub
14. Create a new empty repository at github.com (no README).
15. In the ChargeWise folder:
```bash
git init && git add . && git commit -m "ChargeWise"
git branch -M main
git remote add origin https://github.com/YOUR-USER/chargewise.git
git push -u origin main
```
(`.gitignore` already excludes `.venv`, `node_modules`, `.env`.) Models and `reports/predictions.json` are committed on purpose so the backend starts immediately.

## Part C – Deploy backend on Render (Web Service)
16. render.com → New → Web Service → connect your GitHub repo. Use these values:
| Field | Value |
|---|---|
| Root Directory | *(leave empty – repo root)* |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt && python train.py && python predict.py` |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/health` |
17. **Environment variables** (Render → Environment): `PYTHON_VERSION` = `3.11.9`; `ALLOWED_ORIGINS` = your Vercel URL from step 20 (add after the frontend exists; e.g. `https://chargewise.vercel.app`; several origins separated by commas, no trailing slash). Redeploy after changing it.
18. **Copy the backend URL** (e.g. `https://chargewise-api.onrender.com`). Check `<URL>/api/health`. (Free Render instances sleep; the first request can take ~1 minute.)
Railway alternative: same build/start commands, add the same variables.

## Part D – Deploy frontend on Vercel
19. vercel.com → Add New → Project → import the repo. Settings:
| Field | Value |
|---|---|
| Framework Preset | Vite |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
20. **Environment variable** (Project → Settings → Environment Variables): `VITE_API_URL` = `https://YOUR-BACKEND-URL` (no trailing slash). Then deploy. Copy the Vercel URL and put it in Render's `ALLOWED_ORIGINS` (step 17).
21. **Redeploy** the frontend (Deployments → ⋯ → Redeploy) – Vite bakes `VITE_API_URL` in at build time, so changing it requires a rebuild.
22. Open the production URL.

## Part E – Production test checklist
23. ☐ Map loads with markers ☐ Station list count matches ☐ Click a station → panel ☐ Forecast tab shows 24 bars ☐ Congestion badge ☐ Anomaly (S07 flagged in demo) ☐ Nearby tab lists alternatives for HIGH stations ☐ Hotspots mode shows dashed circles ☐ What-if returns a result ☐ Browser console has no CORS errors.

**Troubleshooting:** CORS error → `ALLOWED_ORIGINS` must exactly equal the Vercel origin (https, no slash). "Cannot reach backend" → wrong `VITE_API_URL` or backend asleep. 503 → predictions missing; check the Render build log for `train.py`/`predict.py` errors.
