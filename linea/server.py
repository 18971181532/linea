"""HTTP server: REST API + static provenance dashboard."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse, parse_qs

from .store import Store
from .lineage import Lineage
from .graph import build_graph
from .verify import verify_run

_WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class ProvenanceHandler(BaseHTTPRequestHandler):
    store: Optional[Store] = None

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/stats":
            return self._json(self.store.stats())

        if path == "/api/runs":
            limit = int(qs.get("limit", ["50"])[0])
            tag = qs.get("tag", [None])[0]
            runs = self.store.list_runs(limit=limit, tag=tag)
            # strip stdout/stderr for list view
            for r in runs:
                r.pop("stdout", None)
                r.pop("stderr", None)
            return self._json(runs)

        if path == "/api/run":
            run_id = qs.get("id", [""])[0]
            run = self.store.get_run(run_id)
            if not run:
                return self._json({"error": "not found"}, 404)
            return self._json(run)

        if path == "/api/graph":
            focus = qs.get("focus", [None])[0]
            max_runs = int(qs.get("max_runs", ["50"])[0])
            return self._json(build_graph(self.store, focus_file=focus, max_runs=max_runs))

        if path == "/api/trace":
            filepath = qs.get("file", [""])[0]
            depth = int(qs.get("depth", ["20"])[0])
            lin = Lineage(self.store)
            return self._json(lin.trace(filepath, max_depth=depth))

        if path == "/api/impact":
            filepath = qs.get("file", [""])[0]
            depth = int(qs.get("depth", ["20"])[0])
            lin = Lineage(self.store)
            return self._json(lin.impact(filepath, max_depth=depth))

        if path == "/api/orphans":
            lin = Lineage(self.store)
            return self._json(lin.orphans())

        if path == "/api/verify":
            run_id = qs.get("run_id", [""])[0]
            result = verify_run(run_id, self.store)
            return self._json(result.to_dict())

        # static
        if path == "/":
            path = "/index.html"
        static = os.path.normpath(os.path.join(_WEB_DIR, path.lstrip("/")))
        if not static.startswith(_WEB_DIR) or not os.path.isfile(static):
            self.send_response(404)
            self.end_headers()
            return
        ext = os.path.splitext(static)[1]
        with open(static, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", _CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(store: Store, host: str = "127.0.0.1", port: int = 8765):
    ProvenanceHandler.store = store
    httpd = ThreadingHTTPServer((host, port), ProvenanceHandler)
    print(f"Linea serving provenance dashboard at http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
