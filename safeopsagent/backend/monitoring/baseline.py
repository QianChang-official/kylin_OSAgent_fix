"""Self-learning metric baselines using median + MAD.

Fixed thresholds ("alert when memory >= 85%") are the least intelligent
part of a monitoring system: a database host that normally sits at 90%
memory is not anomalous, while a host that normally sits at 20% and jumps
to 60% clearly is. This module learns each metric's normal range from its
own history instead.

Method: median and Median Absolute Deviation (MAD). Both are robust to
outliers, which matters because the history inevitably contains the very
spikes we want to detect — a mean/stddev baseline would be dragged toward
the anomalies and stop detecting them.

Anomaly rule (both conditions required):
  1. modified z-score |0.6745 * (x - median) / MAD| >= Z_THRESHOLD
  2. absolute deviation |x - median| >= the metric's minimum delta

Condition 2 exists because MAD approaches zero on a very stable metric,
which makes the z-score explode for a trivially small change. Requiring a
meaningful absolute change is what keeps this from firing constantly on
an idle machine.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

# 0.6745 is the 75th percentile of the standard normal distribution; it
# scales MAD so the resulting score is comparable to a standard z-score.
MAD_SCALE = 0.6745
Z_THRESHOLD = 3.5
MIN_SAMPLES = 12

# Minimum absolute deviation before a metric may be called anomalous.
MIN_DELTA = {
    "cpu_percent": 15.0,
    "mem_percent": 10.0,
    "swap_percent": 10.0,
    "disk_percent": 5.0,
    "load_per_core": 0.5,
}
DEFAULT_MIN_DELTA = 10.0

# Absolute ceilings that are alarming regardless of what is "normal" for
# this host. Learned baselines handle the relative case; these handle the
# case where a host has simply been unhealthy for the whole sample window.
ABSOLUTE_CEILING = {
    "cpu_percent": 95.0,
    "mem_percent": 95.0,
    "swap_percent": 80.0,
    "disk_percent": 90.0,
    "load_per_core": 4.0,
}


@dataclass
class Baseline:
    metric: str
    median: float
    mad: float
    sample_count: int
    lower: float
    upper: float
    learned: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "median": round(self.median, 2),
            "mad": round(self.mad, 3),
            "sample_count": self.sample_count,
            "normal_lower": round(self.lower, 2),
            "normal_upper": round(self.upper, 2),
            "learned": self.learned,
        }


def learn_baseline(metric: str, values: list[float]) -> Baseline:
    """Derive a robust normal range from a metric's own history."""
    clean = [float(v) for v in values if v is not None]
    if len(clean) < MIN_SAMPLES:
        median = statistics.median(clean) if clean else 0.0
        return Baseline(
            metric=metric,
            median=median,
            mad=0.0,
            sample_count=len(clean),
            lower=median,
            upper=median,
            learned=False,
        )

    median = statistics.median(clean)
    mad = statistics.median([abs(value - median) for value in clean])
    min_delta = MIN_DELTA.get(metric, DEFAULT_MIN_DELTA)
    # The normal band is the wider of the statistical band and the minimum
    # delta, so a rock-stable metric does not get an infinitely narrow band.
    half_width = max(mad * Z_THRESHOLD / MAD_SCALE, min_delta)
    return Baseline(
        metric=metric,
        median=median,
        mad=mad,
        sample_count=len(clean),
        lower=max(0.0, median - half_width),
        upper=median + half_width,
        learned=True,
    )


def modified_z_score(value: float, baseline: Baseline) -> float | None:
    if not baseline.learned or baseline.mad <= 0:
        return None
    return round(MAD_SCALE * (value - baseline.median) / baseline.mad, 2)


def evaluate(metric: str, value: float | None, baseline: Baseline) -> dict[str, Any] | None:
    """Return an anomaly record, or None when the value is within normal range.

    Two independent triggers:
      - ``baseline_deviation``: outside the learned normal band for this host
      - ``absolute_ceiling``: alarming in absolute terms regardless of history

    The band test is deliberately used instead of a raw z-score threshold.
    A perfectly stable metric has MAD == 0, which leaves the z-score
    undefined — testing z directly would make such a metric permanently
    unflaggable even when it jumps drastically. The band already folds in
    both the statistical spread and the minimum-delta floor, so it stays
    well-defined at MAD == 0 and matches the band drawn on the dashboard.
    """
    if value is None:
        return None

    ceiling = ABSOLUTE_CEILING.get(metric)
    z_score = modified_z_score(value, baseline)
    deviation = value - baseline.median

    triggered_by: list[str] = []
    if baseline.learned and (value < baseline.lower or value > baseline.upper):
        triggered_by.append("baseline_deviation")
    if ceiling is not None and value >= ceiling:
        triggered_by.append("absolute_ceiling")

    if not triggered_by:
        return None

    if "absolute_ceiling" in triggered_by:
        severity = "critical"
    elif z_score is not None and abs(z_score) >= Z_THRESHOLD * 2:
        severity = "critical"
    elif abs(deviation) >= 2 * max(baseline.upper - baseline.median, 1e-9):
        # Far outside the band even though MAD was too small for a z-score.
        severity = "critical"
    else:
        severity = "warning"

    return {
        "metric": metric,
        "value": round(value, 2),
        "baseline_median": round(baseline.median, 2),
        "normal_lower": round(baseline.lower, 2),
        "normal_upper": round(baseline.upper, 2),
        "deviation": round(deviation, 2),
        "z_score": z_score,
        "severity": severity,
        "triggered_by": triggered_by,
        "sample_count": baseline.sample_count,
        "explanation": _explain(metric, value, baseline, deviation, z_score, triggered_by),
    }


def _explain(
    metric: str,
    value: float,
    baseline: Baseline,
    deviation: float,
    z_score: float | None,
    triggered_by: list[str],
) -> str:
    from .collector import METRIC_LABELS, METRIC_UNITS

    label = METRIC_LABELS.get(metric, metric)
    unit = METRIC_UNITS.get(metric, "")
    direction = "高于" if deviation > 0 else "低于"

    if "absolute_ceiling" in triggered_by and "baseline_deviation" in triggered_by:
        return (
            f"{label} 当前 {value}{unit}，既超过绝对告警线，"
            f"也显著{direction}本机学习基线 {baseline.median}{unit}"
            f"（偏离 {abs(deviation):.1f}{unit}，稳健 z={z_score}）"
        )
    if "absolute_ceiling" in triggered_by:
        return (
            f"{label} 当前 {value}{unit}，超过绝对告警线；"
            f"本机基线为 {baseline.median}{unit}，说明该指标长期处于高位"
        )
    z_text = f"稳健 z={z_score}，" if z_score is not None else "该指标历史极稳定（MAD=0），"
    return (
        f"{label} 当前 {value}{unit}，{direction}本机学习基线 {baseline.median}{unit} "
        f"达 {abs(deviation):.1f}{unit}（{z_text}正常区间 "
        f"{baseline.lower:.1f}~{baseline.upper:.1f}{unit}，基于 {baseline.sample_count} 个历史样本）"
    )
