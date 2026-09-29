"""FastAPI backend. Serves precomputed ML outputs from reports/predictions.json (created by predict.py)."""
import json, os, sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.nearby_alternatives import rank_alternatives  # noqa: E402
from src.geospatial import nearby_stations  # noqa: E402
from src.what_if import simulate  # noqa: E402

PRED = Path(os.getenv("PREDICTIONS_PATH", ROOT / "reports" / "predictions.json"))
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app = FastAPI(title="ChargeWise API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])
_cache = {"mtime": None, "data": None}


def data():
    if not PRED.exists():
        raise HTTPException(503, "Predictions not found. Run `python train.py` then `python predict.py`.")
    m = PRED.stat().st_mtime
    if _cache["mtime"] != m:
        _cache["data"], _cache["mtime"] = json.loads(PRED.read_text()), m
    return _cache["data"]


def station(sid):
    s = data()["stations"].get(sid.upper())
    if not s: raise HTTPException(404, f"Unknown station_id '{sid}'")
    return s


class WhatIfRequest(BaseModel):
    station_id: str
    demand_change_pct: float = Field(0, ge=-50, le=200)
    added_chargers: int = Field(0, ge=-30, le=50)


class Health(BaseModel):
    status: str
    predictions_loaded: bool


@app.get("/api/health", response_model=Health)
def health():
    return Health(status="ok", predictions_loaded=PRED.exists())


@app.get("/api/stations")
def stations():
    d = data()
    keep = ["station_id", "location_name", "latitude", "longitude", "station_type", "chargers", "current_utilization", "predicted_sessions_24h",
            "predicted_energy_kwh_24h", "peak_window", "peak_utilization", "congestion", "congestion_level", "anomaly", "hotspot_id"]
    return {"count": len(d["stations"]), "data_is_synthetic_demo": d["data_is_synthetic_demo"], "coordinate_note": d["coordinate_note"],
            "forecast_start": d["forecast_start"], "stations": [{k: s.get(k) for k in keep} for s in d["stations"].values()]}


@app.get("/api/stations/{station_id}")
def station_detail(station_id: str):
    return station(station_id)


@app.get("/api/stations/{station_id}/forecast")
def forecast(station_id: str):
    s = station(station_id)
    return {"station_id": s["station_id"], "peak_hour": s["peak_hour"], "peak_window": s["peak_window"], "predicted_sessions_24h": s["predicted_sessions_24h"],
            "predicted_energy_kwh_24h": s["predicted_energy_kwh_24h"], "forecast": s["forecast"], "capacity": s["capacity"]}


@app.get("/api/stations/{station_id}/risk")
def risk(station_id: str):
    s = station(station_id)
    return {"station_id": s["station_id"], "congestion": s["congestion"], "peak_utilization": s["peak_utilization"], "chargers": s["chargers"],
            "peak_sessions_per_hour": s["peak_sessions"], "factors": s["factors"],
            "method": "Expected occupancy = predicted arrivals convolved with avg session duration; utilization = occupancy / chargers. LOW<50%, MEDIUM<80%, HIGH<100%, VERY HIGH>=100%."}


@app.get("/api/stations/{station_id}/anomaly")
def anomaly(station_id: str):
    s = station(station_id); return {"station_id": s["station_id"], **s["anomaly"]}


@app.get("/api/stations/{station_id}/nearby")
def nearby(station_id: str, radius_km: float = Query(12, gt=0, le=100), top_k: int = Query(3, ge=1, le=10)):
    s = station(station_id); st = data()["stations"]
    dist = nearby_stations(st, s["station_id"], radius_km)
    alts = rank_alternatives(st, s["station_id"], radius_km, top_k) if s["congestion_level"] >= 2 else []
    msg = None
    if s["congestion_level"] >= 2 and not alts: msg = "No nearby station with spare capacity found within the search radius."
    return {"station_id": s["station_id"], "congestion": s["congestion"], "alternatives_recommended": alts, "message": msg,
            "nearby": [{**n, "congestion": st[n["station_id"]]["congestion"], "location_name": st[n["station_id"]]["location_name"]} for n in dist]}


@app.get("/api/hotspots")
def hotspots():
    d = data(); return {"hotspots": d["hotspots"], "density": d["density"]}


@app.post("/api/what-if")
def what_if(req: WhatIfRequest):
    return simulate(station(req.station_id), req.demand_change_pct, req.added_chargers)


@app.get("/api/summary")
def summary():
    d = data(); s = list(d["stations"].values())
    counts = {}
    for x in s: counts[x["congestion"]] = counts.get(x["congestion"], 0) + 1
    metrics = {}
    mp = ROOT / "reports" / "final" / "metrics.json"
    if mp.exists():
        m = json.loads(mp.read_text())
        metrics = {"sessions_model": m["demand_sessions"]["selected"], "sessions_test": m["demand_sessions"]["results"][m["demand_sessions"]["selected"]].get("test"),
                   "baseline_test": m["demand_sessions"]["results"]["baseline_seasonal_naive"]["test"], "congestion_macro_F1": m["congestion"]["macro_F1"]}
    return {"stations": len(s), "congestion_counts": counts, "anomalies": [x["station_id"] for x in s if x["anomaly"]["flag"]], "hotspots": len(d["hotspots"]),
            "total_predicted_sessions_24h": sum(x["predicted_sessions_24h"] for x in s), "total_predicted_energy_kwh_24h": round(sum(x["predicted_energy_kwh_24h"] for x in s), 1),
            "data_is_synthetic_demo": d["data_is_synthetic_demo"], "model_metrics": metrics}
