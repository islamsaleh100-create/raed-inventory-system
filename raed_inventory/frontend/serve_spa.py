from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SpaHandler(SimpleHTTPRequestHandler):
    backend_origin = "http://localhost:8010"

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request("GET")
            return

        requested = self.translate_path(self.path)
        if os.path.exists(requested):
            super().do_GET()
            return

        self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request("POST")
            return
        self.send_error(405)

    def do_PUT(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request("PUT")
            return
        self.send_error(405)

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request("DELETE")
            return
        self.send_error(405)

    def do_PATCH(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request("PATCH")
            return
        self.send_error(405)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.end_headers()
            return
        self.send_error(405)

    def _proxy_request(self, method: str) -> None:
        body = None
        content_length = self.headers.get("Content-Length")
        if content_length:
            body = self.rfile.read(int(content_length))

        target = f"{self.backend_origin}{self.path}"
        req = Request(target, data=body, method=method)

        for key, value in self.headers.items():
            if key.lower() in {"host", "connection", "content-length"}:
                continue
            req.add_header(key, value)

        try:
            with urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for key, value in resp.getheaders():
                    if key.lower() in {"transfer-encoding", "connection", "content-encoding"}:
                        continue
                    self.send_header(key, value)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp.read())
        except HTTPError as exc:
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() in {"transfer-encoding", "connection", "content-encoding"}:
                    continue
                self.send_header(key, value)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(exc.read())
        except URLError as exc:
            self.send_error(502, f"Backend proxy error: {exc.reason}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--dir", default="dist")
    args = parser.parse_args()

    web_dir = Path(args.dir).resolve()
    handler = lambda *h_args, **h_kwargs: SpaHandler(  # noqa: E731
        *h_args,
        directory=str(web_dir),
        **h_kwargs,
    )

    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving SPA from {web_dir} on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
