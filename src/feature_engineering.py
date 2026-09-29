"""Leakage-safe features: every lag is >= 24h so a 24h-ahead forecast never needs unseen values."""
import numpy as np, pandas as pd

BASE_FEATURES = ["hour_sin", "hour_cos", "dow", "is_weekend", "lag_24", "lag_48", "lag_168",
                 "roll24_lag24", "roll168_lag24", "chargers"]


def make_features(panel, target, stations):
    p = panel.sort_values(["station_id", "timestamp"]).copy()
    g = p.groupby("station_id")[target]
    p["lag_24"], p["lag_48"], p["lag_168"] = g.shift(24), g.shift(48), g.shift(168)
    sh = g.shift(24)
    p["roll24_lag24"] = sh.groupby(p.station_id).transform(lambda x: x.rolling(24, min_periods=1).mean())
    p["roll168_lag24"] = sh.groupby(p.station_id).transform(lambda x: x.rolling(168, min_periods=24).mean())
    h = p.timestamp.dt.hour
    p["hour_sin"], p["hour_cos"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    p["dow"] = p.timestamp.dt.dayofweek; p["is_weekend"] = (p.dow >= 5).astype(int)
    for s in stations: p[f"st_{s}"] = (p.station_id == s).astype(int)
    return p


def feature_cols(stations):
    return BASE_FEATURES + [f"st_{s}" for s in stations]


def chrono_split(df, train=0.70, val=0.15):
    """Chronological split by unique timestamp: older -> train, later -> validation, newest -> test."""
    ts = np.sort(df.timestamp.unique()); a, b = ts[int(len(ts) * train)], ts[int(len(ts) * (train + val))]
    return df[df.timestamp < a], df[(df.timestamp >= a) & (df.timestamp < b)], df[df.timestamp >= b]
