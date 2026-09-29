# ChargeWise – EV Charging Demand & Geospatial Intelligence Platform

> ChargeWise is a geospatial EV charging intelligence platform that combines machine learning, demand forecasting, anomaly detection, and spatial analysis to understand where charging demand is occurring, where future charging pressure may occur, and which nearby alternatives may have available capacity.

**Identity: Geospatial Data Science + Machine Learning.** The map is the main interface, not a dashboard.

> ⚠️ **Data honesty notice.** This repository ships with **no real charging data**. If `data/raw/sessions.csv` is absent, `train.py` generates a clearly-labelled **SYNTHETIC demo dataset** (column `data_source = SYNTHETIC_DEMO`) and **fictional coordinates** (`data/station_locations.csv`). The UI shows a "Demo mode" banner. All numbers below were produced on that synthetic data and say nothing about real-world performance. Replace the data with ACN-Data (below) for real results.

## Problem statement
Operators need to know *where* and *when* charging pressure will occur, which stations behave unusually, and where drivers can be redirected. Static maps and per-station charts don't combine forecasts with geography.

## Why ChargeWise is different
Map-first UI; forecasts, congestion, anomalies, hotspots and *ranked* nearby alternatives are all spatial outputs; what-if scenarios and capacity estimates sit one click from the marker.

## Key features
Map modes (Current Status, Forecast Demand, Congestion Risk, Anomalies, Utilization, Demand Hotspots) · search + filters (congestion, demand, utilization, anomaly, station type) · station intelligence panel · 24h forecast · peak window detection · Isolation-Forest anomalies · nearby alternatives · hotspot detection · what-if simulation · capacity insight · station comparison.

## Architecture
```
data/raw/sessions.csv ─► src/data_loader ─► preprocessing ─► hourly panel ─► feature_engineering
   ─► demand models (sessions, kWh) ─► congestion rule ─► anomaly (IsolationForest)      [train.py]
   ─► predict.py: next-24h forecast + congestion + anomaly + hotspots ─► reports/predictions.json
   ─► FastAPI (backend/main.py) ─► React + Leaflet map (frontend/)
```
Predictions are precomputed by `predict.py` and served from JSON, so the browser never loads raw data.

## Data source
* **Recommended real dataset:** ACN-Data (Caltech Adaptive Charging Network) – https://ev.caltech.edu/dataset. Free for research use after registering for an API token; read and follow its terms of use/citation requirements. I could not download it while building (no internet), so it is **not bundled or tested**.
* **Expected columns** (`data/raw/sessions.csv`): `session_id, station_id, connection_time, disconnect_time, kwh_delivered`.
  Map ACN fields: `sessionID→session_id`, `stationID/spaceID→station_id`, `connectionTime→connection_time`, `disconnectTime→disconnect_time`, `kWhDelivered→kwh_delivered`.
* **Locations:** `data/station_locations.csv` = `station_id, latitude, longitude, location_name, chargers, station_type, coordinate_source`. ACN lacks per-station coordinates and charger counts, so supply your own; the shipped file is **demonstration coordinates** near Chennai, India (fictional siting).

## Preprocessing (src/preprocessing.py)
Parse timestamps; drop missing values, duplicate sessions, non-positive/over-48h durations and non-positive energy; winsorise kWh at the 99.9th percentile; build an hourly station panel (sessions started, kWh, average chargers occupied).

## EDA
`reports/final/eda_overview.png` (hourly profile, daily totals). Extend in `notebooks/` (notebooks were not generated – see Limitations).

## Feature engineering (src/feature_engineering.py)
Cyclical hour, day-of-week, weekend flag, lags of 24/48/168h, rolling means (24h/168h, shifted by 24h), charger count, station one-hot. **All lags are ≥24h**, so a 24h-ahead forecast never needs unseen values (no leakage).

## Chronological split
Train 70% (oldest) → Validation 15% → Test 15% (newest), split by timestamp – never random, which would leak future information. Model choice uses validation only; the winner is refit on train+val and scored once on the untouched test split.

## Demand forecasting results (synthetic demo data, hourly, per station)
| Model | Val MAE | Val RMSE | Test MAE | Test RMSE | Test WAPE |
|---|---|---|---|---|---|
| Seasonal naive (same hour last week) | 0.99 | 1.70 | 1.04 | 1.78 | 69.2% |
| Linear Regression | 0.88 | 1.37 | – | – | – |
| Random Forest | 0.82 | 1.29 | – | – | – |
| **Gradient Boosting (selected, sessions)** | 0.80 | 1.26 | **0.85** | **1.33** | **56.3%** |

Energy (kWh/hour): baseline test MAE 17.80 → Random Forest 14.55. MAPE is not reported because hourly demand contains many zeros (undefined); WAPE is used instead. Hourly counts are inherently noisy (Poisson-like), so ~56% WAPE at hourly resolution is expected; daily totals are much more accurate. Full numbers: `reports/final/metrics.json`.

## Congestion prediction (src/congestion.py) – transparent rule
`expected occupancy_t = Σ predicted arrivals × P(still connected)` using each station's average session duration; `utilization = occupancy / chargers`. Levels: **LOW <50% · MEDIUM 50–80% · HIGH 80–100% · VERY HIGH ≥100%**. The rule applied to *predicted* demand is evaluated against levels derived from *actual* occupancy on the test period: macro-F1 **0.46**, ROC-AUC (utilization ≥80%) **0.93**. Per-class F1: LOW 0.87, MEDIUM 0.24, HIGH 0.15, VERY HIGH 0.59 – the intermediate classes are hard to separate; the model ranks pressure well (AUC) but exact bands are imprecise. Confusion matrix is in metrics.json.

## Anomaly detection (src/anomaly_detection.py)
Isolation Forest (2% contamination) on station-day features (sessions, kWh, peak occupancy, mean duration), normalised by each station's median. The latest day is flagged per station. The app reports observed vs. historical average and **never asserts a cause**. (The demo data has one injected spike at S07 for testing; it is detected.)

## Geospatial analysis
Distances use the Haversine formula (`src/geospatial.py`).
* **Nearby alternatives** (`src/nearby_alternatives.py`): for HIGH/VERY HIGH stations, candidates within 12 km whose congestion is LOW/MEDIUM are ranked by `0.35·proximity + 0.25·(1−utilization) + 0.40·spare capacity` – not simply the nearest.
* **Demand hotspots** (`src/hotspot_detection.py`): DBSCAN (haversine, eps 6 km, ≥2 stations) over stations with HIGH+ predicted congestion; drawn as dashed circles plus a demand-density layer.

## Explainable ML
Global: permutation importance (top features in metrics.json: hour-of-day and 7-day rolling demand dominate). Per station: factors derived from actual data comparisons (recent vs previous week, peak timing, utilization level). SHAP was intentionally not used to keep dependencies small.

## What-if simulation and capacity planning
`POST /api/what-if` rescales predicted demand and/or changes chargers and recomputes utilization/congestion. **This is scenario simulation on model outputs, not a physical experiment.** Capacity insight = extra chargers needed for peak utilization ≤80% – a **model-based planning estimate, not an engineering guarantee**.

## Project structure
```
backend/main.py   FastAPI app          frontend/  React + Vite + react-leaflet
src/              ML + geospatial logic  models/    demand/congestion/anomaly .pkl
train.py          train + evaluate     predict.py  writes reports/predictions.json
data/             raw/, station_locations.csv   reports/  metrics, forecasts, anomalies
```

## Local installation & commands
```bash
# Python 3.10+  (Windows: py -m venv .venv ; .venv\Scripts\activate)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python train.py          # generates demo data if none, trains, saves models + metrics
python predict.py        # writes reports/predictions.json
uvicorn backend.main:app --reload --port 8000     # API docs: http://localhost:8000/docs
# new terminal:
cd frontend && npm install && npm run dev         # http://localhost:5173
```
## API
`GET /api/health · /api/stations · /api/stations/{id} · /{id}/forecast · /{id}/risk · /{id}/anomaly · /{id}/nearby · /api/hotspots · /api/summary` and `POST /api/what-if` (`{station_id, demand_change_pct, added_chargers}`). Errors: 404 unknown station, 422 invalid what-if input, 503 predictions missing.

## Environment variables
| Variable | Where | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | backend | Comma-separated frontend origins for CORS (e.g. `https://chargewise.vercel.app`) |
| `PREDICTIONS_PATH` | backend (optional) | Alternate predictions file |
| `VITE_API_URL` | frontend | Backend base URL (empty in local dev because Vite proxies `/api`) |

## Deployment
See `deployment.md` (Render + Vercel).

## Limitations
* Demo data is synthetic; metrics don't represent real stations. Real-data performance must be re-measured.
* Coordinates are fictional unless you replace them.
* Hourly forecasts are noisy; congestion is a rule, not a learned classifier; MEDIUM/HIGH bands are weak.
* Occupancy of sessions in progress at the end of data is truncated; forecasts are 24h-ahead only; no weather/holiday/price features.
* Anomaly detection is unsupervised; flags mean "unusual", not "faulty".
* Not built: notebooks 01–08, XGBoost/SHAP, GeoPandas (deliberately, to keep dependencies small).
* Predictions are precomputed: re-run `train.py`/`predict.py` after data changes.

## Future improvements
Real ACN/other data, weather/holiday features, quantile forecasts, learned congestion classifier, road-network travel times instead of straight-line distance, scheduled retraining.

## Screenshots
_(Add screenshots here: map overview, station panel, hotspots mode, what-if.)_

## Data interpretation notes
Utilization = average chargers in use ÷ chargers. "Predicted sessions" = sessions expected to *start* in the next 24h. Energy is attributed to the session start hour. Forecasts are model estimates with error, not guarantees.
