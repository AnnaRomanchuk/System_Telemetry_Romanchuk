import time
import socket
import math
import random
import platform
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class TelemetryAgent:
    def __init__(self, host_name: str = None):
        self.host_name = host_name or socket.gethostname()
        self._prev_net = None
        self._simulated_base = {
            "cpu": 35.0,
            "ram": 52.0,
            "disk": 41.0,
            "net_in": 5.0,
            "net_out": 2.0,
        }

    def collect(self) -> dict:
        timestamp = datetime.now().astimezone().isoformat()

        if PSUTIL_AVAILABLE:
            return self._collect_real(timestamp)
        else:
            return self._collect_simulated(timestamp)

    def _collect_real(self, timestamp: str) -> dict:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count()

        mem = psutil.virtual_memory()

        disk_path = "/"
        if platform.system() == "Darwin":
            preferred_path = "/System/Volumes/Data"
            try:
                psutil.disk_usage(preferred_path)
                disk_path = preferred_path
            except Exception:
                disk_path = "/"

        disk = psutil.disk_usage(disk_path)
        disk_io = psutil.disk_io_counters()
        net_now = psutil.net_io_counters()

        net_in_mbps, net_out_mbps = 0.0, 0.0
        now_ts = time.time()

        if self._prev_net is not None:
            prev_recv, prev_sent, prev_ts = self._prev_net
            elapsed = now_ts - prev_ts
            if elapsed > 0:
                net_in_mbps = (net_now.bytes_recv - prev_recv) / elapsed / 1_000_000
                net_out_mbps = (net_now.bytes_sent - prev_sent) / elapsed / 1_000_000

        self._prev_net = (net_now.bytes_recv, net_now.bytes_sent, now_ts)

        total_gb = round(disk.total / 1e9, 2)
        used_gb = round(disk.used / 1e9, 2)
        free_gb = round(total_gb - used_gb, 2)
        usage_pct = round((used_gb / total_gb) * 100, 2) if total_gb > 0 else 0

        return {
            "timestamp": timestamp,
            "host": self.host_name,
            "source": "psutil_agent",
            "cpu": {
                "usage_pct": round(cpu_percent, 2),
                "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
                "core_count": cpu_count,
            },
            "memory": {
                "usage_pct": round(mem.percent, 2),
                "used_mb": round(mem.used / 1e6, 1),
                "total_mb": round(mem.total / 1e6, 1),
                "available_mb": round(mem.available / 1e6, 1),
            },
            "disk": {
                "usage_pct": usage_pct,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "total_gb": total_gb,
                "path": disk_path,
                "read_mb": round(disk_io.read_bytes / 1e6, 2) if disk_io else 0,
                "write_mb": round(disk_io.write_bytes / 1e6, 2) if disk_io else 0,
            },
            "network": {
                "in_mbps": round(net_in_mbps, 3),
                "out_mbps": round(net_out_mbps, 3),
                "bytes_recv_total": net_now.bytes_recv,
                "bytes_sent_total": net_now.bytes_sent,
            },
            "system": {
                "process_count": len(psutil.pids()),
            },
        }

    def _collect_simulated(self, timestamp: str) -> dict:
        t = time.time()
        b = self._simulated_base

        cpu = b["cpu"] + 20 * abs(math.sin(t / 60)) + random.gauss(0, 4)
        ram = b["ram"] + 10 * abs(math.sin(t / 120)) + random.gauss(0, 2)
        disk_pct = b["disk"] + random.gauss(0, 0.3)
        net_in = max(0.1, b["net_in"] + 3 * abs(math.sin(t / 30)) + random.gauss(0, 0.5))
        net_out = max(0.1, b["net_out"] + 1.5 * abs(math.sin(t / 30)) + random.gauss(0, 0.3))

        cpu = round(max(1.0, min(99.0, cpu)), 2)
        ram = round(max(10.0, min(95.0, ram)), 2)
        disk_pct = round(max(5.0, min(95.0, disk_pct)), 2)

        total_gb = 500.0
        used_gb = round(total_gb * disk_pct / 100, 2)
        free_gb = round(total_gb - used_gb, 2)

        return {
            "timestamp": timestamp,
            "host": self.host_name,
            "source": "simulated_agent",
            "cpu": {
                "usage_pct": cpu,
                "freq_mhz": 2400.0,
                "core_count": 4,
            },
            "memory": {
                "usage_pct": ram,
                "used_mb": round(ram * 81.92, 1),
                "total_mb": 8192.0,
                "available_mb": round((100 - ram) * 81.92, 1),
            },
            "disk": {
                "usage_pct": disk_pct,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "total_gb": total_gb,
                "read_mb": round(random.uniform(0, 50), 2),
                "write_mb": round(random.uniform(0, 30), 2),
            },
            "network": {
                "in_mbps": round(net_in, 3),
                "out_mbps": round(net_out, 3),
                "bytes_recv_total": int(t * 1_000_000),
                "bytes_sent_total": int(t * 500_000),
            },
            "system": {
                "process_count": 120 + random.randint(-10, 10),
            },
        }