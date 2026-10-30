"""``python -m repo2ree_testbed.stack.origin_server DIRECTORY PORT``: one stack's origins over HTTP.

Serves the bare repositories under DIRECTORY over git's smart HTTP protocol, by handing
each request to ``git http-backend`` as a CGI program, and every other file under it as
a static file (the fixture tarball). Smart HTTP, not git's own ``git://`` protocol: an
author types an http(s) origin, the GUI accepts nothing else, and the product's shallow,
revision-pinned fetch needs the smart protocol, which a static server cannot speak.
"""

from __future__ import annotations

import os
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

# The request paths git's smart HTTP protocol uses, after the repository's own path.
_GIT_SUFFIXES = ("/info/refs", "/git-upload-pack", "/git-receive-pack", "/HEAD")


class OriginHandler(BaseHTTPRequestHandler):
    root: Path

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path.endswith(_GIT_SUFFIXES):
            self._git(path, url.query)
        else:
            self._static(path)

    def _static(self, path: str) -> None:
        target = (self.root / path.lstrip("/")).resolve()
        if not target.is_relative_to(self.root) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/gzip" if target.suffix == ".gz" else "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _git(self, path: str, query: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "GIT_PROJECT_ROOT": str(self.root),
            "GIT_HTTP_EXPORT_ALL": "1",
            "REQUEST_METHOD": self.command,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(len(body)),
            "REMOTE_ADDR": self.client_address[0],
            # git encodes protocol v2 in this header; the backend reads it from the environment.
            "GIT_PROTOCOL": self.headers.get("Git-Protocol", ""),
        }
        if self.headers.get("Content-Encoding") == "gzip":
            environment["HTTP_CONTENT_ENCODING"] = "gzip"
        result = subprocess.run(["git", "http-backend"], input=body, env=environment, capture_output=True, check=False)
        headers, _, content = result.stdout.partition(b"\r\n\r\n")
        if not _:
            headers, _, content = result.stdout.partition(b"\n\n")
        status = HTTPStatus.OK
        fields: list[tuple[str, str]] = []
        for line in headers.decode("latin-1").splitlines():
            name, _, value = line.partition(":")
            if name.lower() == "status":
                status = HTTPStatus(int(value.split()[0]))
            elif name:
                fields.append((name, value.strip()))
        self.send_response(status)
        for name, value in fields:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the http.server signature
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def main() -> int:
    directory, port = Path(sys.argv[1]).resolve(), int(sys.argv[2])
    handler = type("Handler", (OriginHandler,), {"root": directory})
    # Benches dial in from their containers, as they dial the API.
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)  # noqa: S104 - test stack; reachable by design
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
