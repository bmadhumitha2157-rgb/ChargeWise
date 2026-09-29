"""python train.py  -> loads data, cleans, engineers features, trains + evaluates models, saves models & reports."""
import json, joblib, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, f1_score
from src import data_loader as dl, preprocessing as pp, feature_engineering as fe, demand_forecasting as df_, congestion as cg, anomaly_detection as ad

ROOT = dl.ROOT
def main():
    raw = dl.load_sessions(); loc = dl.load_locations()
    synthetic = dl.is_synthetic(raw)
    sessions, prep = pp.clean_sessions(raw)
    chargers = loc.set_index("station_id").chargers.to_dict(); stations = sorted(loc.station_id)
    panel = pp.build_hourly_panel(sessions, chargers)
    panel.to_csv(ROOT / "data/processed/hourly_panel.csv.gz", index=False)
    cols = fe.feature_cols(stations); metrics = {"data_is_synthetic_demo": synthetic, "preprocessing": prep}
    bundle = {"cols": cols, "stations": stations}
    tests = {}
    for tgt in ["sessions", "kwh"]:
        f = fe.make_features(panel, tgt, stations)
        model, res, te = df_.train_target(f, tgt, cols)
        bundle[f"{tgt}_model"] = model; metrics[f"demand_{tgt}"] = res; tests[tgt] = te
        print(f"[{tgt}] selected={res['selected']}", {k: {s: round(v['MAE'], 3) for s, v in r.items()} for k, r in res['results'].items()})
    joblib.dump(bundle, ROOT / "models/demand_model.pkl", compress=3)

    # ---- congestion: transparent rule evaluated against actual occupancy on the TEST period
    te = tests["sessions"]; t_start = te.timestamp.min()
    dur = sessions[sessions.connection_time < t_start].groupby("station_id").duration_h.mean().to_dict()
    yt, pt, ys, ps = [], [], [], []
    for sid, g in panel.groupby("station_id"):
        g = g.sort_values("timestamp"); arr = g.sessions.values.astype(float)
        pred = te[te.station_id == sid].sort_values("timestamp").pred.values
        arr_p = arr.copy(); arr_p[-len(pred):] = pred
        util_p = cg.expected_occupancy(arr_p, dur[sid])[-len(pred):] / chargers[sid]
        util_a = g.occupancy.values[-len(pred):] / chargers[sid]
        yt += [cg.level(u) for u in util_a]; pt += [cg.level(u) for u in util_p]; ys += list(util_a >= 0.8); ps += list(util_p)
    yt, pt = np.array(yt), np.array(pt)
    cm = confusion_matrix(yt, pt, labels=[0, 1, 2, 3])
    metrics["congestion"] = {"method": "rule on predicted demand x avg duration / chargers", "thresholds": cg.BINS,
        "classification_report": classification_report(yt, pt, labels=[0, 1, 2, 3], target_names=cg.LEVELS, output_dict=True, zero_division=0),
        "macro_F1": float(f1_score(yt, pt, average="macro", labels=[0, 1, 2, 3], zero_division=0)), "confusion_matrix(rows=actual,cols=pred)": cm.tolist(),
        "ROC_AUC_util>=80%": float(roc_auc_score(ys, ps)) if len(set(ys)) > 1 else None}
    print("[congestion] macro-F1", round(metrics["congestion"]["macro_F1"], 3), "AUC", metrics["congestion"]["ROC_AUC_util>=80%"])
    joblib.dump({"thresholds": cg.BINS, "levels": cg.LEVELS, "avg_duration_h": dur}, ROOT / "models/congestion_model.pkl")

    # ---- anomaly detection
    days = ad.station_days(sessions, panel); am, flagged = ad.fit_detect(days)
    joblib.dump(am, ROOT / "models/anomaly_model.pkl", compress=3)
    flagged[flagged.anomaly].to_csv(ROOT / "reports/anomalies/anomalous_station_days.csv", index=False)
    metrics["anomaly"] = {"method": "IsolationForest (unsupervised, contamination=2%)", "station_days": len(days), "flagged": int(flagged.anomaly.sum())}
    print("[anomaly] flagged station-days:", int(flagged.anomaly.sum()))

    # ---- EDA figures
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    panel.assign(h=panel.timestamp.dt.hour).groupby("h").sessions.mean().plot(ax=ax[0], marker="o"); ax[0].set_title("Avg sessions per station-hour"); ax[0].set_xlabel("hour")
    panel.groupby(panel.timestamp.dt.normalize()).sessions.sum().plot(ax=ax[1]); ax[1].set_title("Total sessions per day"); plt.tight_layout()
    plt.savefig(ROOT / "reports/final/eda_overview.png", dpi=110); plt.close()
    (ROOT / "reports/final/metrics.json").write_text(json.dumps(metrics, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("Saved models/ and reports/final/metrics.json")

if __name__ == "__main__":
    main()
