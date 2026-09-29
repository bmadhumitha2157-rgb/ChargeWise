"""Isolation Forest on station-day behaviour, normalised per station so stations are comparable."""
import numpy as np, pandas as pd
from sklearn.ensemble import IsolationForest

COLS = ["sessions", "kwh", "peak_occ", "mean_dur"]


def station_days(sessions, panel):
    d = panel.assign(date=panel.timestamp.dt.normalize()).groupby(["station_id", "date"]).agg(
        sessions=("sessions", "sum"), kwh=("kwh", "sum"), peak_occ=("occupancy", "max")).reset_index()
    sd = sessions.assign(date=sessions.connection_time.dt.normalize()).groupby(["station_id", "date"]).duration_h.mean().rename("mean_dur").reset_index()
    return d.merge(sd, on=["station_id", "date"], how="left").fillna(0)


def _norm(d, ref=None):
    ref = ref if ref is not None else d.groupby("station_id")[COLS].median().clip(lower=1e-6)
    X = d[COLS].values / ref.loc[d.station_id].values
    return X, ref


def fit_detect(days, contamination=0.02, seed=42):
    X, ref = _norm(days)
    m = IsolationForest(n_estimators=200, contamination=contamination, random_state=seed).fit(X)
    out = days.copy(); out["anomaly"] = m.predict(X) == -1; out["score"] = -m.score_samples(X)
    return {"model": m, "ref": ref, "cols": COLS}, out
