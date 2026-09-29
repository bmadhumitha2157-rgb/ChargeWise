"""python predict.py -> next-24h forecast per station + congestion, anomaly, hotspots -> reports/predictions.json"""
import json, joblib, numpy as np, pandas as pd
from src import data_loader as dl, preprocessing as pp, feature_engineering as fe, congestion as cg, hotspot_detection as hd
from src import anomaly_detection as ad, explainability as ex, recommendations as rc

ROOT = dl.ROOT
def fmt_hour(h): return f"{(h % 12) or 12} {'AM' if h % 24 < 12 else 'PM'}"

def main():
    raw = dl.load_sessions(); loc = dl.load_locations().set_index("station_id")
    sessions, _ = pp.clean_sessions(raw); chargers = loc.chargers.to_dict()
    panel = pp.build_hourly_panel(sessions, chargers)
    bundle = joblib.load(ROOT / "models/demand_model.pkl"); cm = joblib.load(ROOT / "models/congestion_model.pkl"); am = joblib.load(ROOT / "models/anomaly_model.pkl")
    stations, cols = bundle["stations"], bundle["cols"]
    last = panel.timestamp.max(); fut = pd.date_range(last + pd.Timedelta(hours=1), periods=24, freq="h")
    ext = pd.concat([panel, pd.DataFrame([{"station_id": s, "timestamp": t, "sessions": np.nan, "kwh": np.nan, "occupancy": np.nan, "chargers": chargers[s]} for s in stations for t in fut])], ignore_index=True)
    pred = {}
    for tgt in ["sessions", "kwh"]:
        f = fe.make_features(ext, tgt, stations); f = f[f.timestamp.isin(fut)].copy()
        f[f"pred_{tgt}"] = np.clip(bundle[f"{tgt}_model"].predict(f[cols].fillna(0)), 0, None); pred[tgt] = f[["station_id", "timestamp", f"pred_{tgt}"]]
    fc = pred["sessions"].merge(pred["kwh"], on=["station_id", "timestamp"]).sort_values(["station_id", "timestamp"])
    fc.to_csv(ROOT / "reports/forecasts/forecast_next24h.csv", index=False)

    days = ad.station_days(sessions, panel); latest = days.date.max()
    X, _ = ad._norm(days, am["ref"]); days["anomaly"] = am["model"].predict(X) == -1; days["score"] = -am["model"].score_samples(X)
    out = {}
    for sid in stations:
        g = fc[fc.station_id == sid]; D = cm["avg_duration_h"][sid]; ch = chargers[sid]
        hist = panel[panel.station_id == sid].sort_values("timestamp")
        occ = cg.expected_occupancy(np.r_[hist.sessions.values, g.pred_sessions.values], D)[-24:]; util = occ / ch
        i = int(np.argmax(g.pred_sessions.values)); pk = float(g.pred_sessions.values[i]); pk_util = float(util.max())
        hours = g.timestamp.dt.hour.values; thr = 0.75 * pk; a = b = i
        while a > 0 and g.pred_sessions.values[a - 1] >= thr: a -= 1
        while b < 23 and g.pred_sessions.values[b + 1] >= thr: b += 1
        ds = days[days.station_id == sid].sort_values("date"); d_last = ds.iloc[-1]; hist_avg = float(ds.iloc[:-1].sessions.mean())
        hist_util = float((hist.occupancy / ch).mean()); cur_util = float(hist.occupancy.tail(3).mean() / ch)
        flag = bool(d_last.anomaly and d_last.date == latest)
        info = {"station_id": sid, "location_name": loc.loc[sid, "location_name"], "latitude": float(loc.loc[sid, "latitude"]), "longitude": float(loc.loc[sid, "longitude"]),
                "station_type": loc.loc[sid, "station_type"], "chargers": int(ch), "avg_duration_h": round(float(D), 2),
                "current_utilization": round(cur_util, 3), "historical_mean_utilization": round(hist_util, 3),
                "predicted_sessions_24h": int(round(g.pred_sessions.sum())), "predicted_energy_kwh_24h": round(float(g.pred_kwh.sum()), 1),
                "peak_sessions": round(pk, 1), "peak_hour": fmt_hour(int(hours[i])), "peak_window": f"{fmt_hour(int(hours[a]))} – {fmt_hour(int(hours[b]) + 1)}",
                "peak_occupancy": round(float(occ.max()), 2), "peak_utilization": round(pk_util, 3), "mean_utilization_24h": round(float(util.mean()), 3),
                "congestion": cg.label(pk_util), "congestion_level": cg.level(pk_util),
                "anomaly": {"flag": flag, "date": str(d_last.date.date()), "observed_sessions": int(d_last.sessions), "historical_avg_sessions_per_day": round(hist_avg, 1), "score": round(float(d_last.score), 3),
                            "message": "Unusual demand pattern detected." if flag else "No unusual pattern detected on the latest day."},
                "forecast": [{"timestamp": str(t), "hour_label": fmt_hour(int(t.hour)), "sessions": round(float(s), 1), "kwh": round(float(k), 1), "utilization": round(float(u), 3)}
                             for t, s, k, u in zip(g.timestamp, g.pred_sessions, g.pred_kwh, util)],
                "capacity": rc.capacity_insight(pk, float(occ.max()), ch),
                "factors": ex.factors(hist, [(int(h), 0) for h in hours[a:b + 1]], pk_util, hist_util)}
        out[sid] = info
    hs = hd.detect_hotspots(out)
    for h in hs:
        for s in h["stations"]: out[s]["hotspot_id"] = h["hotspot_id"]
    res = {"generated_from": str(last), "forecast_start": str(fut[0]), "data_is_synthetic_demo": dl.is_synthetic(raw),
           "coordinate_note": str(pd.read_csv(dl.LOC).coordinate_source.iloc[0]), "stations": out, "hotspots": hs, "density": hd.density_points(out),
           "model_metrics_file": "reports/final/metrics.json"}
    (ROOT / "reports/predictions.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(f"Wrote reports/predictions.json for {len(out)} stations, {len(hs)} hotspot(s)")
    for s in out.values(): print(s["station_id"], s["predicted_sessions_24h"], s["predicted_energy_kwh_24h"], s["peak_window"], s["congestion"], "ANOM" if s["anomaly"]["flag"] else "")

if __name__ == "__main__":
    main()
