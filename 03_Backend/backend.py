#!/usr/bin/env python3
"""Tiny REST backend for the CN project (Team 1).
Run: python3 backend.py A 3001 (Backend A)
     python3 backend.py B 3002 (Backend B)
"""
import datetime
import hashlib
import json
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKEND_ID = sys.argv[1] if len(sys.argv) > 1 else "A"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 3001
HOST = socket.gethostname()

# /api/info is IDENTICAL on both backends, so its ETag is the same
INFO_BODY = json.dumps({
    "project": "Private Network Service Platform",
    "topics": ["DNS", "TCP", "TLS", "HTTP", "Load balancing", "Caching"],
    "version": 1,
}, indent=2).encode()

INFO_ETAG = '"' + hashlib.sha1(INFO_BODY).hexdigest()[:16] + '"'

class Handler(BaseHTTPRequestHandler):
    server_version = "TeamBackend/1.0"

    def reply(self, code, body=b"", ctype="application/json", headers=None):
        self.send_response(code)
        self.send_header("X-Backend", BACKEND_ID)

        for key, value in (headers or {}).items():
            self.send_header(key, value)

        if code != 304:
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))

        self.end_headers()

        if code != 304 and self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        no_store = {"Cache-Control": "no-store"}

        if path == "/":
            html = (
                f"<h1>Backend {BACKEND_ID} is running</h1>"
                f"<p>Host {HOST}, port {PORT}</p>"
                "<p><a href='/api/status'>/api/status</a> | "
                "<a href='/api/info'>/api/info</a></p>"
            )
            self.reply(200, html.encode(), "text/html", no_store)

        elif path == "/api/status":
            data = {
                "backend": BACKEND_ID,
                "status": "ok",
                "host": HOST,
                "port": PORT,
                "time": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            self.reply(200, json.dumps(data).encode(), headers=no_store)

        elif path == "/api/info":
            cache = {
                "Cache-Control": "public, max-age=60",
                "ETag": INFO_ETAG
            }

            if self.headers.get("If-None-Match") == INFO_ETAG:
                self.reply(304, headers=cache)
            else:
                self.reply(200, INFO_BODY, headers=cache)

        else:
            err = {"error": "not found", "backend": BACKEND_ID}
            self.reply(404, json.dumps(err).encode())

    def do_HEAD(self):
        self.do_GET()


if __name__ == "__main__":
    # Listen on ALL interfaces, not only 127.0.0.1
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(
        f"Backend {BACKEND_ID} listening on "
        f"0.0.0.0:{PORT} (Ctrl+C to stop)"
    )
    server.serve_forever()
