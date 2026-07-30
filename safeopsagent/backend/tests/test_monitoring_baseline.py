"""Tests for self-learning metric baselines and the monitoring service.

Covers the innovation claim: anomaly detection derived from each host's
own history (median + MAD) instead of fixed thresholds.
"""
import time

import pytest

from backend.monitoring.baseline import (
    MIN_SAMPLES,
    Z_THRESHOLD,
    evaluate,
    learn_baseline,
    modified_z_score,
)
from backend.monitoring.collector import TRACKED_METRICS, MetricCollector
from backend.monitoring.service import MonitoringService
from backend.monitoring.store import MetricStore


@pytest.fixture()
def store(tmp_path):
    return MetricStore(db_path=tmp_path / "metrics.db", retention=100)


# ---------- baseline learning ----------

def test_baseline_not_learned_below_minimum_samples():
    baseline = learn_baseline("cpu_percent", [10.0] * (MIN_SAMPLES - 1))
    assert baseline.learned is False
    assert baseline.sample_count == MIN_SAMPLES - 1


def test_baseline_learned_at_minimum_samples():
    baseline = learn_baseline("cpu_percent", [10.0] * MIN_SAMPLES)
    assert baseline.learned is True
    assert baseline.median == 10.0


def test_baseline_median_is_robust_to_outliers():
    """A few spikes must not drag the baseline the way a mean would."""
    values = [20.0] * 30 + [99.0] * 5
    baseline = learn_baseline("cpu_percent", values)
    mean = sum(values) / len(values)
    assert baseline.median == 20.0
    assert baseline.median < mean  # mean is pulled up by the spikes, median is not


def test_high_but_stable_host_is_not_anomalous():
    """A DB host that always sits at 90% memory is normal for that host.

    This is the case a fixed 85% threshold gets wrong.
    """
    baseline = learn_baseline("mem_percent", [89.0, 90.0, 91.0, 90.0, 89.5] * 6)
    assert evaluate("mem_percent", 90.0, baseline) is None


def test_low_baseline_host_flags_moderate_value():
    """The same 60% that is normal elsewhere is anomalous on a quiet host."""
    baseline = learn_baseline("mem_percent", [20.0, 21.0, 19.0, 20.5, 20.0] * 6)
    anomaly = evaluate("mem_percent", 60.0, baseline)
    assert anomaly is not None
    assert "baseline_deviation" in anomaly["triggered_by"]
    assert anomaly["deviation"] > 0


def test_tiny_change_on_stable_metric_is_not_flagged():
    """MAD near zero must not make a trivial change explode into an alert."""
    baseline = learn_baseline("mem_percent", [50.0, 50.0, 50.1, 49.9, 50.0] * 6)
    # z-score would be enormous here, but the absolute delta is meaningless.
    assert evaluate("mem_percent", 51.0, baseline) is None


def test_absolute_ceiling_fires_even_when_host_is_always_unhealthy():
    """A host at 97% memory for its whole history is still critical."""
    baseline = learn_baseline("mem_percent", [96.0, 97.0, 98.0, 97.0] * 8)
    anomaly = evaluate("mem_percent", 97.0, baseline)
    assert anomaly is not None
    assert anomaly["triggered_by"] == ["absolute_ceiling"]
    assert anomaly["severity"] == "critical"


def test_perfectly_stable_metric_still_flags_a_large_jump():
    """Regression: MAD == 0 leaves the z-score undefined.

    A metric pinned at exactly 37% has MAD 0. Testing the z-score directly
    would make it permanently unflaggable — a jump to 91% would be silently
    ignored, even though it sits far outside the band drawn on screen.
    The band test must fire here.
    """
    baseline = learn_baseline("mem_percent", [37.0] * 40)
    assert baseline.mad == 0.0
    assert modified_z_score(91.0, baseline) is None  # undefined, by construction

    anomaly = evaluate("mem_percent", 91.0, baseline)
    assert anomaly is not None, "a 37% → 91% jump must not be silently ignored"
    assert "baseline_deviation" in anomaly["triggered_by"]
    assert anomaly["severity"] == "critical"
    assert "MAD=0" in anomaly["explanation"]


def test_stable_metric_band_still_respects_minimum_delta():
    """The MAD == 0 fix must not make trivial changes noisy."""
    baseline = learn_baseline("mem_percent", [37.0] * 40)
    # Inside the min-delta floor band (37 ± 10) — must stay silent.
    assert evaluate("mem_percent", 40.0, baseline) is None
    assert evaluate("mem_percent", 45.0, baseline) is None
    # Outside it — must fire.
    assert evaluate("mem_percent", 55.0, baseline) is not None


def test_evaluate_returns_none_for_missing_value():
    baseline = learn_baseline("cpu_percent", [10.0] * 20)
    assert evaluate("cpu_percent", None, baseline) is None


def test_modified_z_score_none_when_not_learned():
    baseline = learn_baseline("cpu_percent", [1.0, 2.0])
    assert modified_z_score(5.0, baseline) is None


def test_anomaly_explanation_mentions_baseline_and_sample_count():
    baseline = learn_baseline("cpu_percent", [10.0, 11.0, 9.0, 10.5] * 8)
    anomaly = evaluate("cpu_percent", 80.0, baseline)
    assert anomaly is not None
    assert "基线" in anomaly["explanation"]
    assert str(baseline.sample_count) in anomaly["explanation"]


def test_severity_escalates_with_extreme_deviation():
    baseline = learn_baseline("cpu_percent", [10.0, 11.0, 9.0, 10.5] * 8)
    mild = evaluate("cpu_percent", 30.0, baseline)
    extreme = evaluate("cpu_percent", 85.0, baseline)
    assert mild is not None and extreme is not None
    assert abs(extreme["z_score"]) > abs(mild["z_score"]) >= Z_THRESHOLD
    assert extreme["severity"] == "critical"


# ---------- store ----------

def test_store_records_and_reads_series(store):
    now = time.time()
    for index in range(5):
        store.record(now + index, {"cpu_percent": float(index * 10)})
    series = store.series("cpu_percent")
    assert len(series) == 5
    assert series[0]["value"] == 0.0      # oldest first for chart rendering
    assert series[-1]["value"] == 40.0


def test_store_skips_none_values(store):
    stored = store.record(time.time(), {"cpu_percent": 5.0, "swap_percent": None})
    assert stored == 1
    assert store.count("swap_percent") == 0


def test_store_latest_returns_newest(store):
    now = time.time()
    store.record(now, {"cpu_percent": 1.0})
    store.record(now + 10, {"cpu_percent": 2.0})
    assert store.latest("cpu_percent")["value"] == 2.0


def test_store_prune_enforces_retention_per_metric(tmp_path):
    store = MetricStore(db_path=tmp_path / "m.db", retention=10)
    now = time.time()
    for index in range(25):
        store.record(now + index, {"cpu_percent": float(index), "mem_percent": float(index)})
    store.prune()
    # Retention is applied per metric, so neither series evicts the other.
    assert store.count("cpu_percent") == 10
    assert store.count("mem_percent") == 10


def test_store_latest_none_when_empty(store):
    assert store.latest("cpu_percent") is None


# ---------- collector ----------

def test_collector_returns_all_tracked_metrics():
    sample = MetricCollector().collect()
    assert set(sample.values.keys()) == set(TRACKED_METRICS)


def test_collector_cpu_needs_two_samples():
    """First collection primes the delta; it cannot report a rate yet."""
    collector = MetricCollector()
    first = collector.collect()
    assert first.values["cpu_percent"] is None


def test_collector_reports_source():
    sample = MetricCollector().collect()
    assert sample.source in {"/proc", "win32", "unsupported"}


# ---------- service ----------

def test_service_sample_once_persists(tmp_path):
    service = MonitoringService(store=MetricStore(db_path=tmp_path / "m.db"))
    service.sample_once()
    result = service.sample_once()
    assert "sample" in result
    assert service.store.count() > 0


def test_service_anomalies_empty_without_history(tmp_path):
    service = MonitoringService(store=MetricStore(db_path=tmp_path / "m.db"))
    service.sample_once()
    # A single sample cannot support a learned baseline.
    assert service.anomalies() == []


def test_service_detects_injected_anomaly(tmp_path):
    service = MonitoringService(store=MetricStore(db_path=tmp_path / "m.db"))
    now = time.time()
    for index in range(30):
        service.store.record(now + index, {"mem_percent": 20.0 + (index % 3)})
    service.store.record(now + 100, {"mem_percent": 75.0})

    anomalies = service.anomalies()
    memory = [item for item in anomalies if item["metric"] == "mem_percent"]
    assert memory, "a 75% reading against a ~20% baseline must be flagged"
    assert memory[0]["severity"] in {"warning", "critical"}


def test_service_metrics_payload_shape(tmp_path):
    service = MonitoringService(store=MetricStore(db_path=tmp_path / "m.db"))
    service.store.record(time.time(), {"cpu_percent": 12.0})
    payload = service.metrics_payload()
    assert set(payload["metrics"].keys()) == set(TRACKED_METRICS)
    cpu = payload["metrics"]["cpu_percent"]
    assert cpu["latest"] == 12.0
    assert "baseline" in cpu and "points" in cpu


def test_service_overview_health_reflects_anomalies(tmp_path):
    service = MonitoringService(store=MetricStore(db_path=tmp_path / "m.db"))
    now = time.time()
    for index in range(30):
        service.store.record(now + index, {"mem_percent": 20.0 + (index % 3)})
    assert service.overview()["health"] == "healthy"

    service.store.record(now + 100, {"mem_percent": 97.0})
    overview = service.overview()
    assert overview["health"] == "critical"
    assert overview["anomaly_count"] >= 1


def test_service_sampler_not_running_by_default(tmp_path):
    """Importing/constructing must never start background work on its own."""
    service = MonitoringService(store=MetricStore(db_path=tmp_path / "m.db"))
    assert service.is_running() is False


# ---------- HTTP API ----------

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from backend.app import app
    return TestClient(app)


def test_monitor_sample_endpoint(client):
    response = client.post("/monitor/sample")
    assert response.status_code == 200
    assert "sample" in response.json()


def test_monitor_overview_endpoint(client):
    payload = client.get("/monitor/overview").json()
    assert payload["health"] in {"healthy", "warning", "critical"}
    assert "host" in payload and "system" in payload["host"]


def test_monitor_metrics_endpoint(client):
    payload = client.get("/monitor/metrics").json()
    assert set(payload["metrics"].keys()) == set(TRACKED_METRICS)
    for metric in payload["metrics"].values():
        assert "points" in metric and "baseline" in metric and "label" in metric


def test_monitor_anomalies_endpoint(client):
    payload = client.get("/monitor/anomalies").json()
    assert isinstance(payload["anomalies"], list)


def test_monitor_endpoints_do_not_start_sampler(client):
    """TestClient without lifespan must not spawn the sampling thread."""
    from backend.monitoring import get_monitoring_service
    client.get("/monitor/overview")
    assert get_monitoring_service().is_running() is False
