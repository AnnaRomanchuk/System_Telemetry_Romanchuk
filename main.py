import argparse
import time
import webbrowser
import threading

from agent import TelemetryAgent
from alerts import AlertEngine
from data_base import TSDBStorage
from server import CollectorServer


def parse_args():
    parser = argparse.ArgumentParser(
        description="Система телеметрії — головний модуль"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Інтервал збору метрик у секундах"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Порт HTTP-сервера"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Не відкривати браузер автоматично"
    )
    return parser.parse_args()


def print_metrics(metrics: dict, alerts: list):
    ts = metrics["timestamp"][11:19]
    cpu = metrics["cpu"]["usage_pct"]
    ram = metrics["memory"]["usage_pct"]
    net = metrics["network"]["in_mbps"]

    dsk = metrics["disk"]["usage_pct"]
    used = metrics["disk"]["used_gb"]
    free = metrics["disk"]["free_gb"]
    total = metrics["disk"]["total_gb"]

    status = ""
    if alerts:
        worst = max(
            alerts,
            key=lambda a: {"CRITICAL": 2, "WARNING": 1}.get(a["severity"], 0)
        )
        status = f"  ⚠ {worst['severity']}: {worst['metric']} = {worst['value']}%"

    print(
        f"[{ts}] CPU {cpu:5.1f}%  RAM {ram:5.1f}%  "
        f"Net ↓{net:.2f} MB/s  Disk {dsk:5.1f}% "
        f"(used {used:.1f} / free {free:.1f} / total {total:.1f} GB){status}"
    )


def main():
    args = parse_args()

    agent = TelemetryAgent()
    engine = AlertEngine(cooldown_sec=30)
    storage = TSDBStorage(max_points=1500)
    server = CollectorServer(tsdb=storage, host=agent.host_name, port=args.port)

    print("=" * 60)
    print(f"  Хост:     {agent.host_name}")
    print(f"  Інтервал: {args.interval} с")

    server.start()
    print()

    if not args.no_browser:
        def open_browser():
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{args.port}/")
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        while True:
            metrics = agent.collect()
            alerts = engine.check(metrics)
            storage.write(metrics)
            server.push_alerts(alerts)
            print_metrics(metrics, alerts)
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nЗупинено.")
    finally:
        server.stop()


if __name__ == "__main__":
    main()