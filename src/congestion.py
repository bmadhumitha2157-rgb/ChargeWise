"""Transparent congestion rule.
Expected occupancy (chargers busy) = arrivals/hour convolved over the average session duration (Little-style queue occupancy).
Utilization = occupancy / chargers.  LOW <50%, MEDIUM 50-80%, HIGH 80-100%, VERY HIGH >100% (demand exceeds capacity)."""
import numpy as np
LEVELS = ["LOW", "MEDIUM", "HIGH", "VERY HIGH"]
BINS = [0.5, 0.8, 1.0]


def utilization(arrivals_per_hour, avg_duration_h, chargers):
    return np.asarray(arrivals_per_hour) * avg_duration_h / np.maximum(chargers, 1)


def level(util):
    return int(np.digitize(util, BINS))


def label(util):
    return LEVELS[level(util)]


def extra_chargers_needed(peak_occupancy, chargers, target_util=0.8):
    return int(max(0, np.ceil(peak_occupancy / target_util - chargers)))


def expected_occupancy(arrivals, avg_duration_h):
    """Expected chargers in use per hour from an arrivals-per-hour series (history + forecast).
    An arrival k hours ago is still connected for a fraction clip(D-k, 0, 1) of the hour (arrivals in the same hour count half)."""
    a = np.asarray(arrivals, float); D = float(avg_duration_h)
    w = [min(D, 1.0) * 0.5] + [float(np.clip(D - k, 0, 1)) for k in range(1, int(np.ceil(D)) + 1)]
    return np.convolve(a, w)[: len(a)]
