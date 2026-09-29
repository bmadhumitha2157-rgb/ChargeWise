"""Demand models: seasonal baseline (same hour last week) vs Linear / RandomForest / GradientBoosting.
Model selection on the VALIDATION split; final model refit on train+val; metrics reported on the untouched TEST split."""
import numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.inspection import permutation_importance
from .feature_engineering import chrono_split


def _metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return {"MAE": float(mean_absolute_error(y, p)), "RMSE": float(np.sqrt(mean_squared_error(y, p))),
            "WAPE_%": float(100 * np.abs(y - p).sum() / max(y.sum(), 1e-9))}  # MAPE undefined at zero-demand hours -> WAPE


def candidates():
    return {"LinearRegression": LinearRegression(),
            "RandomForest": RandomForestRegressor(n_estimators=150, max_depth=14, min_samples_leaf=3, n_jobs=-1, random_state=42),
            "GradientBoosting": HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, random_state=42)}


def baseline_pred(df):
    return df["lag_168"].fillna(df["lag_24"]).fillna(0).values


def train_target(feat_df, target, cols):
    d = feat_df.dropna(subset=["lag_168", "roll168_lag24"]).copy()
    tr, va, te = chrono_split(d)
    res = {"baseline_seasonal_naive": {"validation": _metrics(va[target], baseline_pred(va)), "test": _metrics(te[target], baseline_pred(te))}}
    fitted = {}
    for name, m in candidates().items():
        m.fit(tr[cols], tr[target]); pv = np.clip(m.predict(va[cols]), 0, None)
        res[name] = {"validation": _metrics(va[target], pv)}; fitted[name] = m
    best = min(fitted, key=lambda k: res[k]["validation"]["MAE"])
    final = candidates()[best].fit(pd.concat([tr, va])[cols], pd.concat([tr, va])[target])
    pt = np.clip(final.predict(te[cols]), 0, None)
    res[best]["test"] = _metrics(te[target], pt)
    imp = permutation_importance(final, te[cols].iloc[::4], te[target].iloc[::4], n_repeats=3, random_state=42, n_jobs=-1)
    fi = {c: float(v) for c, v in sorted(zip(cols, imp.importances_mean), key=lambda x: -x[1])[:8]}
    split = {"train_end": str(va.timestamp.min()), "val_end": str(te.timestamp.min()), "test_end": str(te.timestamp.max())}
    return final, {"selected": best, "results": res, "permutation_importance_top": fi, "split": split}, te.assign(pred=pt)
