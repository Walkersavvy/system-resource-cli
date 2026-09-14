"""Tests for cloudres.resources: snapshot sampling and threshold checks."""
from cloudres import resources


def test_take_snapshot_returns_expected_fields():
    snap = resources.take_snapshot(cpu_interval=0.05)
    assert 0.0 <= snap.cpu_percent <= 100.0
    assert snap.cpu_count >= 1
    assert 0.0 <= snap.mem_percent <= 100.0
    assert 0.0 <= snap.disk_percent <= 100.0
    assert snap.mem_total_mb > 0
    assert snap.net_bytes_sent >= 0
    assert snap.net_bytes_recv >= 0
    assert snap.hostname


def test_snapshot_to_dict_is_json_friendly():
    snap = resources.take_snapshot(cpu_interval=0.05)
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert d["cpu_percent"] == snap.cpu_percent
    assert "timestamp" in d


def test_check_against_limits_detects_breach():
    snap = resources.take_snapshot(cpu_interval=0.05)
    # Force a breach by setting an impossible-to-miss low threshold.
    limits = {"cpu_percent": -1}
    breaches = resources.check_against_limits(snap, limits)
    assert breaches["cpu_percent"] is True


def test_check_against_limits_no_breach_when_under_threshold():
    snap = resources.take_snapshot(cpu_interval=0.05)
    limits = {"mem_percent": 1000}  # unreachable threshold
    breaches = resources.check_against_limits(snap, limits)
    assert breaches["mem_percent"] is False


def test_check_against_limits_ignores_unknown_metric():
    snap = resources.take_snapshot(cpu_interval=0.05)
    limits = {"not_a_real_metric": 50}
    breaches = resources.check_against_limits(snap, limits)
    assert breaches == {}
