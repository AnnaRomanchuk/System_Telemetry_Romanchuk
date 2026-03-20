"""
data_base.py — Рівень 3: In-memory база даних часових рядів
TSDBStorage зберігає метрики у вигляді іменованих часових серій
і надає Prometheus-сумісний формат для HTTP-експорту.
"""

from collections import deque


DEFAULT_MAX_POINTS = 1200


class TSDBStorage:
    """
    In-memory база даних часових рядів.
    Кожна серія — черга deque(maxlen=max_points) пар (timestamp, value).
    """

    def __init__(self, max_points: int = DEFAULT_MAX_POINTS):
        self.max_points = max_points
        self._series: dict[str, deque] = {}

    # ── Запис ─────────────────────────────────────────────────────

    def write(self, metrics: dict):
        ts = metrics["timestamp"]
        host = metrics["host"]

        entries = {
            "cpu.usage_pct": metrics["cpu"]["usage_pct"],
            "memory.usage_pct": metrics["memory"]["usage_pct"],
            "memory.used_mb": metrics["memory"]["used_mb"],
            "memory.total_mb": metrics["memory"]["total_mb"],

            "disk.usage_pct": metrics["disk"]["usage_pct"],
            "disk.used_gb": metrics["disk"]["used_gb"],
            "disk.free_gb": metrics["disk"]["free_gb"],
            "disk.total_gb": metrics["disk"]["total_gb"],

            "network.in_mbps": metrics["network"]["in_mbps"],
            "network.out_mbps": metrics["network"]["out_mbps"],
            "system.process_count": metrics["system"]["process_count"],
        }

        for name, value in entries.items():
            key = f"{host}.{name}"
            if key not in self._series:
                self._series[key] = deque(maxlen=self.max_points)
            self._series[key].append((ts, value))

    # ── Читання ───────────────────────────────────────────────────

    def query(self, host: str, series: str, last_n: int = None) -> list[tuple]:
        data = list(self._series.get(f"{host}.{series}", []))
        return data[-last_n:] if last_n else data

    def latest(self, host: str, series: str):
        row = self.query(host, series, last_n=1)
        return row[0][1] if row else None

    def all_series(self) -> list[str]:
        return list(self._series.keys())

    def snapshot(self, host: str) -> dict:
        result = {}
        prefix = f"{host}."
        for key, dq in self._series.items():
            if key.startswith(prefix) and dq:
                series_name = key[len(prefix):]
                result[series_name] = dq[-1][1]
        return result

    # ── Prometheus-сумісний експорт ───────────────────────────────

    def export_prometheus(self, host: str) -> str:
        metrics_map = {
            "cpu.usage_pct": ("telemetry_cpu_usage_pct", "CPU utilization percent"),
            "memory.usage_pct": ("telemetry_memory_usage_pct", "RAM utilization percent"),
            "memory.used_mb": ("telemetry_memory_used_mb", "RAM used MB"),
            "memory.total_mb": ("telemetry_memory_total_mb", "RAM total MB"),
            "disk.usage_pct": ("telemetry_disk_usage_pct", "Disk used percent"),
            "disk.used_gb": ("telemetry_disk_used_gb", "Disk used GB"),
            "disk.free_gb": ("telemetry_disk_free_gb", "Disk free GB"),
            "disk.total_gb": ("telemetry_disk_total_gb", "Disk total GB"),
            "network.in_mbps": ("telemetry_network_in_mbps", "Network inbound MB/s"),
            "network.out_mbps": ("telemetry_network_out_mbps", "Network outbound MB/s"),
            "system.process_count": ("telemetry_system_process_count", "Running processes"),
        }

        lines = []
        for series_suffix, (prom_name, help_text) in metrics_map.items():
            val = self.latest(host, series_suffix)
            if val is not None:
                lines += [
                    f"# HELP {prom_name} {help_text}",
                    f"# TYPE {prom_name} gauge",
                    f'{prom_name}{{host="{host}"}} {val}',
                ]

        return "\n".join(lines) + "\n"