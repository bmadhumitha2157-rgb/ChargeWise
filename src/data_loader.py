"""Data loading. Uses data/raw/sessions.csv. If missing, a clearly-labelled SYNTHETIC demo dataset is generated.
Expected columns: session_id, station_id, connection_time, disconnect_time, kwh_delivered
Real data: convert ACN-Data (https://ev.caltech.edu/dataset) JSON/CSV to these columns (see README)."""
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "sessions.csv"
LOC = ROOT / "data" / "station_locations.csv"
REQUIRED = ["session_id", "station_id", "connection_time", "disconnect_time", "kwh_delivered"]

# id, name, lat, lon, chargers, type  (DEMONSTRATION coordinates - fictional siting, not real stations)
STATIONS = [
    ("S01", "Central Plaza Hub", 13.0827, 80.2707, 12, "retail"),
    ("S02", "Tech Park North", 13.1067, 80.2206, 16, "workplace"),
    ("S03", "Riverside Residency", 13.0569, 80.2425, 8, "residential"),
    ("S04", "Airport Road Stop", 13.0012, 80.2565, 10, "retail"),
    ("S05", "Industrial Estate", 13.1215, 80.2870, 14, "workplace"),
    ("S06", "Lakeview Apartments", 13.0333, 80.2100, 6, "residential"),
    ("S07", "Market Street", 13.0710, 80.2600, 8, "retail"),
    ("S08", "University Gate", 13.0450, 80.2950, 10, "workplace"),
    ("S09", "Highway Junction", 13.1400, 80.2300, 12, "retail"),
    ("S10", "Garden Colony", 13.0900, 80.3050, 6, "residential"),
    ("S11", "Business Tower", 13.0780, 80.2450, 14, "workplace"),
    ("S12", "Harbour Point", 13.1000, 80.3000, 8, "retail"),
]
_H = np.arange(24)
PROFILE = {  # relative hourly arrival profiles
    "workplace": np.exp(-0.5 * ((_H - 9) / 2.0) ** 2) + 0.25 * np.exp(-0.5 * ((_H - 13) / 2) ** 2) + 0.02,
    "residential": np.exp(-0.5 * ((_H - 19) / 2.2) ** 2) + 0.15 * np.exp(-0.5 * ((_H - 7) / 1.5) ** 2) + 0.03,
    "retail": np.exp(-0.5 * ((_H - 13) / 3.5) ** 2) + 0.7 * np.exp(-0.5 * ((_H - 18) / 2.0) ** 2) + 0.05,
}
DUR = {"workplace": 6.0, "residential": 4.5, "retail": 1.3}  # mean hours
BASE = {"workplace": 2.6, "residential": 2.0, "retail": 3.0}


def generate_demo(days=120, seed=42):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-03-01")
    rows = []
    for sid, name, lat, lon, ch, typ in STATIONS:
        scale = ch / 10 * rng.uniform(0.8, 1.25)
        for d in range(days):
            day = start + pd.Timedelta(days=d)
            wk = day.dayofweek >= 5
            f = (0.55 if (wk and typ == "workplace") else 1.15 if (wk and typ != "workplace") else 1.0)
            trend = 1 + 0.003 * d
            spike = 3.0 if (sid == "S07" and d == days - 1) else 1.0  # injected anomaly for demo
            for h in range(24):
                lam = BASE[typ] * PROFILE[typ][h] * scale * f * trend * spike * 0.9
                for _ in range(rng.poisson(lam)):
                    t0 = day + pd.Timedelta(hours=h, minutes=float(rng.uniform(0, 59)))
                    dur = float(np.clip(rng.lognormal(np.log(DUR[typ]), 0.4), 0.25, 14))
                    kwh = float(np.clip(dur * rng.uniform(3, 7), 1, 60))
                    rows.append((sid, t0, t0 + pd.Timedelta(hours=dur), round(kwh, 2)))
    df = pd.DataFrame(rows, columns=["station_id", "connection_time", "disconnect_time", "kwh_delivered"])
    df.insert(0, "session_id", [f"D{i:06d}" for i in range(len(df))])
    df["data_source"] = "SYNTHETIC_DEMO"
    RAW.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW, index=False)
    loc = pd.DataFrame(STATIONS, columns=["station_id", "location_name", "latitude", "longitude", "chargers", "station_type"])
    loc["coordinate_source"] = "DEMONSTRATION (fictional coordinates, not real stations)"
    loc.to_csv(LOC, index=False)
    return df


def load_sessions():
    if not RAW.exists():
        print("[data] No raw data found -> generating SYNTHETIC demo dataset (NOT real-world data).")
        generate_demo()
    df = pd.read_csv(RAW)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"sessions.csv missing columns: {missing}")
    return df


def load_locations():
    if not LOC.exists():
        raise FileNotFoundError("data/station_locations.csv missing (station_id, latitude, longitude, location_name, chargers, station_type)")
    return pd.read_csv(LOC)


def is_synthetic(df):
    return "data_source" in df.columns and (df["data_source"] == "SYNTHETIC_DEMO").all()
