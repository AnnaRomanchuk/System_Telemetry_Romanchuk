import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from data_base import TSDBStorage


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        self.query_params = parse_qs(parsed.query)

        routes = {
            "/metrics": self._metrics,
            "/api/latest": self._api_latest,
            "/api/history": self._api_history,
            "/": self._dashboard,
        }

        handler = routes.get(path, self._not_found)

        try:
            handler()
        except Exception as e:
            self._respond(500, "text/plain", f"Server error: {e}".encode("utf-8"))

    def _metrics(self):
        body = self.server.tsdb.export_prometheus(self.server.agent_host)
        self._respond(
            200,
            "text/plain; version=0.0.4; charset=utf-8",
            body.encode("utf-8")
        )


    def _api_latest(self):
        snap = self.server.tsdb.snapshot(self.server.agent_host)

        data = {
            "host": self.server.agent_host,
            "metrics": snap,
            "alerts": self.server.latest_alerts,
        }
        self._json(data)

    def _api_history(self):
        host = self.server.agent_host
        tsdb = self.server.tsdb

        try:
            limit = int(self.query_params.get("limit", ["300"])[0])
        except ValueError:
            limit = 300

        limit = max(10, min(limit, 1500))

        series_names = [
            "cpu.usage_pct",
            "memory.usage_pct",
            "network.in_mbps",
            "network.out_mbps",
        ]

        history = {}
        for s in series_names:
            rows = tsdb.query(host, s, last_n=limit)
            history[s] = [{"t": ts, "v": v} for ts, v in rows]

        self._json({
            "host": host,
            "history": history,
            "limit": limit,
        })

    def _dashboard(self):
        html_path = Path(__file__).parent / "dashboard.html"
        if not html_path.exists():
            self._respond(404, "text/plain", b"dashboard.html not found")
            return

        body = html_path.read_bytes()
        self._respond(200, "text/html; charset=utf-8", body)

    def _not_found(self):
        self._respond(404, "text/plain", b"Not Found")


    def _json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._respond(200, "application/json; charset=utf-8", body)

    def _respond(self, code: int, content_type: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class CollectorServer:

    def __init__(self, tsdb: TSDBStorage, host: str, port: int = 8000):
        self.tsdb = tsdb
        self.host = host
        self.port = port
        self._httpd = None
        self.latest_alerts: list[dict] = []

    def start(self):
        self._httpd = HTTPServer(("0.0.0.0", self.port), _Handler)
        self._httpd.tsdb = self.tsdb
        self._httpd.agent_host = self.host
        self._httpd.latest_alerts = self.latest_alerts

        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()

        print(f"  Dashboard:    http://localhost:{self.port}/")
        print(f"  API latest:   http://localhost:{self.port}/api/latest")
        print(f"  API history:  http://localhost:{self.port}/api/history?limit=300")
        print(f"  Prometheus:   http://localhost:{self.port}/metrics")

    def push_alerts(self, alerts: list[dict]):
        self.latest_alerts.clear()
        self.latest_alerts.extend(alerts[-20:])

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()