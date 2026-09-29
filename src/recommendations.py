from .congestion import extra_chargers_needed


def capacity_insight(peak_sessions, peak_occupancy, chargers):
    occ = peak_occupancy
    add = extra_chargers_needed(occ, chargers)
    msg = ("Additional charging capacity may be considered for the predicted peak period." if add else "Current capacity appears sufficient for the predicted peak period.")
    return {"peak_predicted_sessions_per_hour": round(peak_sessions, 1), "current_chargers": chargers, "estimated_additional_chargers": add,
            "message": msg, "disclaimer": "Model-based planning estimate (target peak utilization 80%), not an engineering guarantee."}
