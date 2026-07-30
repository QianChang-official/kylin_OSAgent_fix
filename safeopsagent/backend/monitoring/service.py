"""Monitoring service: sampling loop, dashboard payloads, baseline anomalies.

The sampler runs as a daemon thread started from the FastAPI lifespan hook,
so importing the app (as tests do) never spawns background work.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from .baseline import Baseline, evaluate, learn_baseline
from .collector import (
    METRIC_LABELS,
    METRIC_UNITS,
    TRACKED_METRICS,
    MetricCollector,
    host_overview,
)
from .store import MetricStore

SAMPLE_INTERVAL_SECONDS = float(os.environ.get("MONITOR_SAMPLE_INTERVAL", "60"))
SAMPLING_ENABLED = os.environ.get("MONITOR_SAMPLING_ENABLED", "1") != "0"
PRUNE_EVERY_SAMPLES = 60


class MonitoringService:
    def __init__(self, store: MetricStore | None = None,
                 collector: MetricCollector | None = None) -> None:
        self.store = store or MetricStore()
        self.collector = collector or MetricCollector()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._samples_since_prune = 0
        self._lock = threading.Lock()

    # ---------- sampling ----------

    def sample_once(self) -> dict[str, Any]:
        """Collect and persist a single sample."""
        reading = self.collector.collect()
        stored = self.store.record(reading.ts, reading.values)
        with self._lock:
            self._samples_since_prune += 1
            should_prune = self._samples_since_prune >= PRUNE_EVERY_SAMPLES
            if should_prune:
                self._samples_since_prune = 0
        if should_prune:
            self.store.prune()
        return {"sample": reading.to_dict(), "stored_metrics": stored}

    def start(self, interval: float = SAMPLE_INTERVAL_SECONDS) -> bool:
        """Start the background sampler. Returns False if already running."""
        if not SAMPLING_ENABLED:
            return False
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, args=(interval,), name="monitor-sampler", daemon=True
            )
            self._thread.start()
        return True

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self, interval: float) -> None:
        # Prime the CPU delta immediately so the first stored sample is usable.
        self.collector.collect()
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception:
                # A sampling failure must never kill the loop or the service.
                pass
            self._stop.wait(max(1.0, interval))

    # ---------- dashboard payloads ----------

    def baselines(self) -> dict[str, Baseline]:
        return {
            metric: learn_baseline(metric, self.store.values(metric))
            for metric in TRACKED_METRICS
        }

    def anomalies(self) -> list[dict[str, Any]]:
        """Current baseline deviations, most severe first."""
        found: list[dict[str, Any]] = []
        for metric, baseline in self.baselines().items():
            latest = self.store.latest(metric)
            if not latest:
                continue
            anomaly = evaluate(metric, latest["value"], baseline)
            if anomaly:
                anomaly["ts"] = latest["ts"]
                anomaly["label"] = METRIC_LABELS.get(metric, metric)
                found.append(anomaly)
        found.sort(key=lambda item: (item["severity"] != "critical", -abs(item["deviation"])))
        return found

    def metrics_payload(self, points: int = 120) -> dict[str, Any]:
        total_samples = self.store.count()
        series = {}
        for metric in TRACKED_METRICS:
            baseline = learn_baseline(metric, self.store.values(metric))
            latest = self.store.latest(metric)
            metric_samples = self.store.count(metric)
            # A metric with zero samples while others have data is not
            # "still learning" — this platform cannot report it at all.
            available = metric_samples > 0 or total_samples == 0
            series[metric] = {
                "label": METRIC_LABELS.get(metric, metric),
                "unit": METRIC_UNITS.get(metric, ""),
                "points": self.store.series(metric, limit=points),
                "latest": latest["value"] if latest else None,
                "baseline": baseline.to_dict(),
                "available": available,
                "sample_count": metric_samples,
            }
        return {
            "metrics": series,
            "tracked": list(TRACKED_METRICS),
            "sample_count": total_samples,
            "sampler_running": self.is_running(),
            "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
            "collector_source": self.collector.collect().source,
        }

    def overview(self) -> dict[str, Any]:
        anomalies = self.anomalies()
        if any(item["severity"] == "critical" for item in anomalies):
            health = "critical"
        elif anomalies:
            health = "warning"
        else:
            health = "healthy"
        return {
            "host": host_overview(),
            "health": health,
            "anomaly_count": len(anomalies),
            "sample_count": self.store.count(),
            "sampler_running": self.is_running(),
            "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
            "collector_source": self.collector.collect().source,
        }


_service: MonitoringService | None = None
_service_lock = threading.Lock()


def get_monitoring_service() -> MonitoringService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = MonitoringService()
    return _service
