"""Serve track_annotator.html with a save endpoint.

    python3 serve_annotator.py                 # this machine only
    python3 serve_annotator.py --lan           # reachable from your phone

Static files are served from train_detection/, so the tool can read the
reference frames in working_images/ and any existing camera_tracks.json.
POSTing to /save-tracks writes camera_tracks.json back to disk.

--lan binds every interface so a phone on the same Wi-Fi can trace rails
by touch, which is far easier than a trackpad. That also means anything
else on the network can reach the save endpoint and overwrite the traces,
so use it on a network you trust and stop the server when you are done.
"""

import argparse
import json
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
TRACKS_PATH = HERE / 'camera_tracks.json'
NOTE = ('Track centrelines in 854x480 image space, ordered from the Bishops '
        'Lydeard end towards Minehead. Traced with track_annotator.html.')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def do_POST(self):
        if self.path != '/save-tracks':
            self.send_error(404)
            return
        length = int(self.headers.get('Content-Length', 0))
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self.send_error(400, 'invalid JSON')
            return
        payload['_note'] = NOTE
        TRACKS_PATH.write_text(json.dumps(payload, indent=1))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"saved": true}')

    def log_message(self, format, *args):
        pass   # keep the console quiet


def lan_address() -> str | None:
    """Best guess at this machine's address on the local network."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('192.0.2.1', 1))     # TEST-NET-1: routed nowhere
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--lan', action='store_true',
                        help='bind all interfaces so a phone can reach it')
    args = parser.parse_args()

    host = '0.0.0.0' if args.lan else '127.0.0.1'
    server = ThreadingHTTPServer((host, args.port), Handler)
    path = f'/track_annotator.html'
    print(f'annotator: http://127.0.0.1:{args.port}{path}')
    if args.lan:
        address = lan_address()
        if address:
            print(f'on your phone: http://{address}:{args.port}{path}')
        print('serving to the whole local network — stop the server when done')
    server.serve_forever()


if __name__ == '__main__':
    main()
