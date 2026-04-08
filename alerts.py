import time
from datetime import datetime, timezone

THRESHOLDS = {
    "cpu_warn":  70.0,   # % попередження
    "cpu_crit":  85.0,   # % критичне
    "ram_warn":  75.0,
    "ram_crit":  90.0,
    "disk_warn": 75.0,
    "disk_crit": 90.0,
}


class AlertEngine:
    INFO     = "INFO"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"

    def __init__(self, cooldown_sec: int = 30):
        self.cooldown_sec = cooldown_sec
        self._last_fired: dict[str, float] = {}

    def check(self, metrics: dict) -> list[dict]:

        alerts = []
        host = metrics.get("host", "unknown")
        now  = time.monotonic()

        checks = [
            ("cpu",  metrics["cpu"]["usage_pct"],    THRESHOLDS["cpu_warn"],  THRESHOLDS["cpu_crit"]),
            ("ram",  metrics["memory"]["usage_pct"], THRESHOLDS["ram_warn"],  THRESHOLDS["ram_crit"]),
            ("disk", metrics["disk"]["usage_pct"],   THRESHOLDS["disk_warn"], THRESHOLDS["disk_crit"]),
        ]

        for metric_name, value, warn, crit in checks:
            alert = self._evaluate(
                key=f"{host}.{metric_name}",
                host=host,
                metric=metric_name.upper(),
                value=value,
                warn=warn,
                crit=crit,
                now=now,
            )
            if alert:
                alerts.append(alert)

        return alerts

    def _evaluate(self, key, host, metric, value, warn, crit, now) -> (dict |
    None):
        if value >= crit:
            severity = self.CRITICAL
            threshold = crit
            msg = (f"{host}: {metric} = {value}% — критичний поріг {crit}% "
    f"перевищено")
        elif value >= warn:
            severity = self.WARNING
            threshold = warn
            msg = f"{host}: {metric} = {value}% — попереджувальний поріг {warn}%"
        else:
            return None

        if now - self._last_fired.get(key, 0) < self.cooldown_sec:
            return None

        self._last_fired[key] = now
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity":  severity,
            "host":      host,
            "metric":    metric,
            "value":     value,
            "threshold": threshold,
            "message":   msg,
        }