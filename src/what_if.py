"""Scenario simulation on the model's forecast (NOT a physical experiment)."""
import numpy as np
from .congestion import label, level, extra_chargers_needed


def simulate(station, demand_change_pct=0.0, added_chargers=0):
    f = 1 + demand_change_pct / 100.0
    ch = max(1, station["chargers"] + added_chargers)
    peak = station["peak_sessions"] * f
    occ = station["peak_occupancy"] * f  # expected chargers busy at peak, scaled by demand
    util = occ / ch
    return {"station_id": station["station_id"], "note": "Scenario simulation based on model forecasts - not a real-world experiment.",
            "current": {"chargers": station["chargers"], "sessions_24h": station["predicted_sessions_24h"], "peak_utilization": station["peak_utilization"], "congestion": station["congestion"]},
            "scenario": {"chargers": ch, "sessions_24h": int(round(station["predicted_sessions_24h"] * f)), "energy_kwh_24h": round(station["predicted_energy_kwh_24h"] * f, 1),
                         "peak_utilization": round(float(util), 3), "congestion": label(util), "congestion_level": level(util),
                         "additional_chargers_suggested": extra_chargers_needed(occ, ch)},
            "inputs": {"demand_change_pct": demand_change_pct, "added_chargers": added_chargers}}
