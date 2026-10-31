"""
Minimal CS2-style web server. CS2-compatible software (TrainControl, the CS2
App, ...) doesn't only use CAN-over-UDP: it also decides whether an IP is a
Central Station by fetching files over HTTP from the station -- TrainControl
pings /can/ at startup and treats a host as a station if
/config/gleisbild.cs2 answers 200, then reads lokomotive.cs2,
magnetartikel.cs2, fahrstrassen.cs2 and gleisbilder/*.cs2 from /config/.

This serves a directory of real CS2 files (default /var/lib/pitraincontroller/cs2,
laid out as it would be on a CS2: config/lokomotive.cs2, ...). Anything
missing from that directory falls back to a minimal empty-but-valid default so
the station is recognised; copy real files into the directory to give clients
a loco/accessory/route list.

Run via: python -m pitraincontroller.gateway.webconfig
(wired up as pitraincontroller-cs2web.service in systemd/)
"""

from __future__ import annotations

import logging
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

logging.basicConfig(
    level=os.environ.get("PITC_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("pitraincontroller.cs2web")

WEB_PORT = int(os.environ.get("PITC_WEB_PORT", "80"))
WEB_ROOT = os.environ.get("PITC_WEB_ROOT", "/var/lib/pitraincontroller/cs2")

_DEFAULTS: dict[str, bytes] = {
    "/can/": b"PiTrainController CAN gateway\n",
    "/config/gleisbild.cs2": b"[gleisbild]\nversion\n .major=1\n",
    "/config/lokomotive.cs2": b"[lokomotive]\nversion\n .minor=3\nsession\n .id=1\n",
    "/config/magnetartikel.cs2": b"[magnetartikel]\nversion\n .minor=1\nsession\n .id=1\n",
    "/config/fahrstrassen.cs2": b"[fahrstrassen]\nversion\n .minor=1\nsession\n .id=1\n",
    "/config/geraet.vrs": b"[geraet]\nversion\n .minor=1\ngeraet\n .sernum=1\n .hardvers=PiTrainController,1\n",
}


def default_body(path: str) -> bytes | None:
    """The built-in fallback for a request path, or None if there isn't one."""
    p = unquote(urlsplit(path).path)
    if p == "/can":
        p = "/can/"
    return _DEFAULTS.get(p)


class Cs2WebHandler(SimpleHTTPRequestHandler):
    server_version = "PiTrainController-CS2"

    def _file_exists(self) -> bool:
        return os.path.isfile(self.translate_path(self.path))

    def _send_default(self, body: bytes, head_only: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        body = default_body(self.path)
        if body is not None and not self._file_exists():
            self._send_default(body, head_only=False)
        else:
            super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        body = default_body(self.path)
        if body is not None and not self._file_exists():
            self._send_default(body, head_only=True)
        else:
            super().do_HEAD()

    def log_message(self, format: str, *args: object) -> None:
        log.debug("%s - %s", self.address_string(), format % args)


def make_server(port: int, root: str, host: str = "") -> ThreadingHTTPServer:
    handler = partial(Cs2WebHandler, directory=root)
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    os.makedirs(WEB_ROOT, exist_ok=True)
    server = make_server(WEB_PORT, WEB_ROOT)
    log.info("CS2 web config server on port %d, serving %s", WEB_PORT, WEB_ROOT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
