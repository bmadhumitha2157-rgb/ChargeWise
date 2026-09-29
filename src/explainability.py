"""Data-derived (not fabricated) contributing factors. Global model importance is saved by train.py (permutation importance)."""
import pandas as pd


def factors(station_panel, forecast_hours, peak_util, hist_util_mean):
    out = []
    ph = [h for h, _ in forecast_hours]
    if any(17 <= h <= 21 for h in ph): out.append("Evening peak in forecast window")
    elif any(8 <= h <= 11 for h in ph): out.append("Morning peak in forecast window")
    d = station_panel.assign(date=station_panel.timestamp.dt.normalize()).groupby("date").sessions.sum()
    if len(d) >= 14:
        r, p = d.iloc[-7:].mean(), d.iloc[-14:-7].mean()
        if p > 0 and r / p > 1.05: out.append(f"Increasing recent demand (+{(r/p-1)*100:.0f}% vs previous week)")
        elif p > 0 and r / p < 0.95: out.append(f"Decreasing recent demand ({(r/p-1)*100:.0f}% vs previous week)")
        if r > d.mean() * 1.05: out.append("High recent demand vs station history")
    if peak_util >= 0.8: out.append("Predicted peak utilization near/above capacity")
    if hist_util_mean >= 0.5: out.append("High historical utilization")
    return out or ["No dominant factor identified"]
