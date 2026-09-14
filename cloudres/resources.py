"""System resource sampling.

Wraps psutil to produce a plain-dict snapshot of CPU, memory, disk, and
network usage that's easy to serialize to JSON or compare against
threshold limits from a cloud config file.
"""
from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

import psutil


@dataclass
class ResourceSnapshot:
    timestamp: float
    cpu_percent: float
    cpu_count: int
    load_avg: Optional[list]
    mem_total_mb: float
    mem_used_mb: float
    mem_percent: float
    swap_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    net_bytes_sent: int
    net_bytes_recv: int
    hostname: str = field(default_factory=platform.node)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_average() -> Optional[list]:
    # os.getloadavg() isn't available on Windows.
    getloadavg = getattr(psutil, "getloadavg", None)
    if getloadavg is None:
        return None
    try:
        return list(getloadavg())
    except (OSError, AttributeError):
        return None


def take_snapshot(disk_path: str = "/", cpu_interval: float = 0.3) -> ResourceSnapshot:
    """Sample current system resource usage.

    cpu_interval: seconds to block while psutil measures CPU percent.
    A short nonzero interval gives a meaningful (non-zero-on-first-call) reading.
    """
    cpu_percent = psutil.cpu_percent(interval=cpu_interval)
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage(disk_path)
    net = psutil.net_io_counters()

    return ResourceSnapshot(
        timestamp=time.time(),
        cpu_percent=cpu_percent,
        cpu_count=psutil.cpu_count(logical=True) or 0,
        load_avg=_load_average(),
        mem_total_mb=round(vm.total / (1024 ** 2), 1),
        mem_used_mb=round(vm.used / (1024 ** 2), 1),
        mem_percent=vm.percent,
        swap_percent=swap.percent,
        disk_total_gb=round(disk.total / (1024 ** 3), 2),
        disk_used_gb=round(disk.used / (1024 ** 3), 2),
        disk_percent=disk.percent,
        net_bytes_sent=net.bytes_sent,
        net_bytes_recv=net.bytes_recv,
    )


def check_against_limits(snapshot: ResourceSnapshot, limits: Dict[str, Any]) -> Dict[str, bool]:
    """Compare a snapshot against config['limits'] thresholds.

    limits example: {"cpu_percent": 85, "mem_percent": 90, "disk_percent": 95}
    Returns a dict of {metric: breached_bool} for each configured limit.
    """
    field_map = {
        "cpu_percent": snapshot.cpu_percent,
        "mem_percent": snapshot.mem_percent,
        "disk_percent": snapshot.disk_percent,
        "swap_percent": snapshot.swap_percent,
    }
    breaches = {}
    for key, threshold in limits.items():
        if key in field_map:
            breaches[key] = field_map[key] >= threshold
    return breaches
