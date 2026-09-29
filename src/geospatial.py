import numpy as np


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return float(2 * R * np.arcsin(np.sqrt(a)))


def nearby_stations(stations, station_id, radius_km=12.0):
    """All stations within radius with real haversine distances (sorted by distance)."""
    s = stations[station_id]
    out = [{"station_id": k, "distance_km": round(haversine_km(s["latitude"], s["longitude"], v["latitude"], v["longitude"]), 2)}
           for k, v in stations.items() if k != station_id]
    return sorted([o for o in out if o["distance_km"] <= radius_km], key=lambda x: x["distance_km"])
