"""Moving a file between the bench and the control plane beside the control socket.

Out of the bench (``ExecUploadRequest``) the workbench ``PUT``s a file; into it
(``FetchFileRequest``) it ``GET``s one. The workbench only ever dials out, so both go
where its control socket goes: the same host and port, over HTTP(S) instead of
WS(S), to the transfer path the control plane named. Files stream from and to disk;
TCP flow control paces them, and nothing about them can delay a keepalive ping on
the socket. Standard library only: the bench's closure carries no HTTP client.
"""

from __future__ import annotations

import http.client
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_SCHEMES = {"ws": "http", "wss": "https", "http": "http", "https": "https"}


def transfer_url(api_ws_url: str, transfer_path: str) -> str:
    """The HTTP URL of ``transfer_path`` on the control plane this workbench dialed at ``api_ws_url``."""
    dialed = urlsplit(api_ws_url)
    if dialed.scheme not in _SCHEMES or not transfer_path.startswith("/"):
        raise ValueError(f"cannot address transfer {transfer_path!r} on {api_ws_url!r}")
    return urlunsplit((_SCHEMES[dialed.scheme], dialed.netloc, transfer_path, "", ""))


def upload_file(path: Path, url: str, timeout: float = 600.0) -> None:
    """``PUT`` the file to ``url``; raises unless the control plane took all of it."""
    target = urlsplit(url)
    connection_type = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(target.netloc, timeout=timeout)
    try:
        with path.open("rb") as body:
            connection.request(
                "PUT",
                target.path,
                body=body,
                headers={"Content-Type": "application/octet-stream", "Content-Length": str(path.stat().st_size)},
            )
        response = connection.getresponse()
        response.read()
        if response.status >= 300:
            raise RuntimeError(f"the control plane refused the upload: HTTP {response.status}")
    finally:
        connection.close()


def download_file(url: str, target: Path, timeout: float = 600.0) -> None:
    """``GET`` the file at ``url`` into ``target``; raises unless all of it arrived."""
    source = urlsplit(url)
    connection_type = http.client.HTTPSConnection if source.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(source.netloc, timeout=timeout)
    try:
        connection.request("GET", source.path)
        response = connection.getresponse()
        if response.status != 200:
            response.read()
            raise RuntimeError(f"the control plane refused the download: HTTP {response.status}")
        expected = response.getheader("Content-Length")
        size = 0
        with target.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                size += len(chunk)
        if expected is not None and size != int(expected):
            raise RuntimeError(f"the download ended after {size} of {expected} bytes")
    finally:
        connection.close()
