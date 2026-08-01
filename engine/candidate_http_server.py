#!/usr/bin/env python3
"""Serve a candidate archive over loopback HTTP for installation testing."""

import argparse
import signal
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        print(f"http: {self.address_string()} {format % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("port_file", type=Path)
    args = parser.parse_args()
    handler = partial(_Handler, directory=str(args.directory.resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address
    args.port_file.write_text(str(port), encoding="ascii")
    print(f"Serving {args.directory.resolve()} at http://{host}:{port}", flush=True)
    def stop_server(_signal_number, _frame) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
