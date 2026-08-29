"""Serve track_annotator.html with a save endpoint.

    python3 serve_annotator.py [--port 8090]

Static files are served from train_detection/, so the tool can read the
reference frames in working_images/ and any existing camera_tracks.json.
POSTing to /save-tracks writes camera_tracks.json back to disk.
"""

import argparse
import json
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'annotator: http://127.0.0.1:{args.port}/track_annotator.html')
    server.serve_forever()


if __name__ == '__main__':
    main()
