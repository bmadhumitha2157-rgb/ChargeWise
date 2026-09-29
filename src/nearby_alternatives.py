"""Rank alternatives by a blend of proximity and availability - NOT just nearest.
score = 0.35*distance_term + 0.25*predicted_utilization_term + 0.40*spare_capacity_term  (higher is better)
Only stations whose congestion is LOW/MEDIUM are eligible."""
from .geospatial import nearby_stations

W_DIST, W_UTIL, W_SPARE = 0.35, 0.25, 0.40


def rank_alternatives(stations, station_id, radius_km=12.0, top_k=3):
    near = nearby_stations(stations, station_id, radius_km)
    res = []
    for n in near:
        s = stations[n["station_id"]]
        if s["congestion_level"] >= 2: continue
        spare = max(0.0, s["chargers"] * (1 - s["peak_utilization"]))
        res.append({**n, "location_name": s["location_name"], "chargers": s["chargers"], "peak_utilization": s["peak_utilization"],
                    "congestion": s["congestion"], "spare_chargers_at_peak": round(spare, 1),
                    "_dt": 1 - n["distance_km"] / radius_km, "_ut": 1 - min(s["peak_utilization"], 1.0), "_sp": spare})
    if not res: return []
    mx = max(r["_sp"] for r in res) or 1.0
    for r in res:
        r["score"] = round(W_DIST * r.pop("_dt") + W_UTIL * r.pop("_ut") + W_SPARE * r.pop("_sp") / mx, 3)
    return sorted(res, key=lambda r: -r["score"])[:top_k]
