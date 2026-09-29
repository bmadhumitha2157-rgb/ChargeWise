"""Validation, cleaning and hourly panel construction."""
import numpy as np, pandas as pd


def clean_sessions(df):
    rep = {"rows_raw": len(df)}
    df = df.copy()
    df["connection_time"] = pd.to_datetime(df["connection_time"], errors="coerce")
    df["disconnect_time"] = pd.to_datetime(df["disconnect_time"], errors="coerce")
    df["kwh_delivered"] = pd.to_numeric(df["kwh_delivered"], errors="coerce")
    n = len(df); df = df.dropna(subset=["station_id", "connection_time", "disconnect_time", "kwh_delivered"])
    rep["dropped_missing"] = n - len(df)
    n = len(df); df = df.drop_duplicates(subset=["session_id"]).drop_duplicates(subset=["station_id", "connection_time", "disconnect_time"])
    rep["dropped_duplicates"] = n - len(df)
    df["duration_h"] = (df["disconnect_time"] - df["connection_time"]).dt.total_seconds() / 3600
    n = len(df); df = df[(df.duration_h > 0.05) & (df.duration_h <= 48) & (df.kwh_delivered > 0)]
    rep["dropped_invalid_duration_or_energy"] = n - len(df)
    cap = df["kwh_delivered"].quantile(0.999)  # winsorise extreme energy values instead of dropping
    rep["kwh_winsor_cap"] = float(cap); df["kwh_delivered"] = df["kwh_delivered"].clip(upper=cap)
    rep["rows_clean"] = len(df)
    return df.reset_index(drop=True), rep


def build_hourly_panel(sessions, chargers):
    """One row per station-hour: sessions started, kWh (attributed to start hour), occupancy (avg chargers in use)."""
    s = sessions.copy(); s["hour"] = s.connection_time.dt.floor("h")
    t0, t1 = s.hour.min(), s.hour.max()
    idx = pd.date_range(t0, t1, freq="h")
    out = []
    for sid, g in s.groupby("station_id"):
        agg = g.groupby("hour").agg(sessions=("session_id", "count"), kwh=("kwh_delivered", "sum")).reindex(idx, fill_value=0)
        occ = np.zeros(len(idx))
        for a, b in zip(g.connection_time, g.disconnect_time):
            i0 = int((a.floor("h") - t0) / pd.Timedelta(hours=1)); i1 = int((b.floor("h") - t0) / pd.Timedelta(hours=1))
            for i in range(i0, min(i1, len(idx) - 1) + 1):
                lo = max(a, idx[i]); hi = min(b, idx[i] + pd.Timedelta(hours=1))
                if hi > lo: occ[i] += (hi - lo).total_seconds() / 3600
        agg["occupancy"] = occ; agg["station_id"] = sid; agg["timestamp"] = idx
        out.append(agg.reset_index(drop=True))
    p = pd.concat(out, ignore_index=True)
    p["chargers"] = p.station_id.map(chargers)
    # drop the final partial day tail (sessions still running) so occupancy is not truncated
    return p[p.timestamp <= p.timestamp.max() - pd.Timedelta(hours=0)].reset_index(drop=True)
