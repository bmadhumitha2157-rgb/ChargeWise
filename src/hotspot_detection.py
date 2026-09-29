"""Demand hotspots: DBSCAN (haversine) on stations under pressure (predicted peak utilization >= 80%),
plus a density grid of predicted 24h demand used for the heat layer."""
import numpy as np
from sklearn.cluster import DBSCAN
from .geospatial import haversine_km


def detect_hotspots(stations, eps_km=6.0, min_stations=2):
    ids = [k for k, v in stations.items() if v["congestion_level"] >= 2]
    if len(ids) < min_stations: return []
    X = np.radians([[stations[i]["latitude"], stations[i]["longitude"]] for i in ids])
    lab = DBSCAN(eps=eps_km / 6371.0088, min_samples=min_stations, metric="haversine").fit_predict(X)
    out = []
    for c in sorted(set(lab) - {-1}):
        m = [ids[i] for i in range(len(ids)) if lab[i] == c]
        w = np.array([stations[i]["predicted_sessions_24h"] for i in m], float)
        lat = float(np.average([stations[i]["latitude"] for i in m], weights=w)); lon = float(np.average([stations[i]["longitude"] for i in m], weights=w))
        rad = max(haversine_km(lat, lon, stations[i]["latitude"], stations[i]["longitude"]) for i in m) + 0.8
        out.append({"hotspot_id": f"H{len(out)+1}", "latitude": lat, "longitude": lon, "radius_km": round(rad, 2), "stations": m,
                    "predicted_sessions_24h": int(w.sum()), "predicted_energy_kwh_24h": round(sum(stations[i]["predicted_energy_kwh_24h"] for i in m), 1),
                    "message": "High predicted demand is concentrated in this geographical area."})
    return sorted(out, key=lambda h: -h["predicted_sessions_24h"])


def density_points(stations):
    tot = sum(s["predicted_sessions_24h"] for s in stations.values()) or 1
    return [{"latitude": s["latitude"], "longitude": s["longitude"], "weight": round(s["predicted_sessions_24h"] / tot, 4)} for s in stations.values()]
