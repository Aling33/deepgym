"""Serve ./app on 127.0.0.1:8000 and save each POST /api/state body to ./state.json.

Single-threaded on purpose: saves apply in arrival order, and each one replaces
state.json atomically so the verifier never reads a half-written file.
"""

import http.server
import os
from functools import partial
from pathlib import Path

STATE = Path('state.json').resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != '/api/state':
            self.send_error(404)
            return
        tmp = STATE.with_suffix('.tmp')
        tmp.write_bytes(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        os.replace(tmp, STATE)
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


http.server.HTTPServer(
    ('127.0.0.1', 8000), partial(Handler, directory=str(Path('app').resolve()))
).serve_forever()
