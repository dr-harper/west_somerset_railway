"""Capture frames from the WSR live webcams for train detection.

The West Somerset Railway cameras (run by Railcam UK) are public 24/7
YouTube Live streams on the "RailcamLive - WSR" channel. yt-dlp resolves
each stream to an HLS manifest that OpenCV can read directly, so frames
can be fed straight into a detection model.

Requires: pip install yt-dlp opencv-python, and a JavaScript runtime for
yt-dlp to solve YouTube's player challenge — Node is used here.

Usage:
    from wsr_live_capture import open_stream, grab_frame, CAMERAS

    frame = grab_frame('minehead_station')       # one BGR numpy array

    cap = open_stream('blue_anchor')             # or keep a stream open
    ok, frame = cap.read()
"""

import os
import random
import threading
from pathlib import Path
import time

import cv2
import yt_dlp


def _node() -> dict:
    """Where node actually is, rather than trusting PATH.

    Naming the runtime alone was enough from a terminal and not enough
    from launchd, which runs with PATH=/usr/bin:/bin:/usr/sbin:/sbin —
    node lives in /opt/homebrew/bin, so yt-dlp found no runtime, fell
    back to the deprecated path and returned 'This live stream recording
    is not available' for every camera. The 08:00 start on 31/8 produced
    nothing for this reason. An absolute path cannot be lost that way.
    """
    import shutil
    found = shutil.which('node') or next(
        (p for p in ('/opt/homebrew/bin/node', '/usr/local/bin/node')
         if Path(p).exists()), None)
    return {'path': found} if found else {}



# All eleven WSR cameras Railcam publish, verified live 29th August 2026.
# Ordered along the line from the Bishops Lydeard end towards Minehead.
# Second angles at Crowcombe, Watchet and Blue Anchor give a station two
# independent views, which is what settles an ambiguous direction.
CAMERAS = {
    'bishops_lydeard': 'hEa16bHxHMM',
    'crowcombe_heathfield': 'ptn6Fnc5u08',
    'crowcombe_heathfield_2': 'x-OipExeKQM',
    'williton': '77rYzQYyQYQ',
    'williton_2': 'YHILlgN9cFs',
    'watchet_1': 'yCoeSJjUsDg',
    'watchet_visitor_centre': 'lHPtw6tKigc',
    'blue_anchor': 'oURn7l3gpr4',
    'blue_anchor_2': 'CDO4ObH-O5k',
    'minehead_seaward_crossing': 'cO1MFjvfKUE',
    'minehead_station': 'k40FIAhyhjo',
}

# Cameras with a hand-validated northbound vector, so drift alone gives a
# direction. The watcher runs every camera in CAMERAS regardless; the rest
# report 'unclear' and take their direction from the order of stations a
# movement visits. Do not add a camera here on the strength of a traced
# centreline: the tangent gives the right axis but not reliably the right
# sign, and at Minehead it points the opposite way.
CALIBRATED = {
    'bishops_lydeard', 'crowcombe_heathfield', 'watchet_visitor_centre',
    'blue_anchor', 'minehead_seaward_crossing', 'minehead_station',
}

# HLS format ids: 231 = 854x480, 230 = 640x360, 232 = 1280x720
DEFAULT_FORMAT = '231/230/229'


# One extraction returns every rendition, so cache the whole format table
# per camera. Resolving once per camera per CACHE_TTL_S — instead of once
# per stream open — keeps request volume low enough to avoid YouTube's
# bot challenge (which we tripped on 29/8 at ~110 resolves in a day).
CACHE_TTL_S = 3 * 3600
_cache: dict[str, tuple[float, dict[str, str]]] = {}
_cache_lock = threading.Lock()

# Resolutions are serialised and spaced out. Six cameras cold-starting
# together is what tripped the challenge on 29/8: the watcher restarted,
# asked YouTube for all six at once, and every camera was refused for the
# rest of the evening.
_resolve_lock = threading.Lock()
_last_resolve = 0.0
RESOLVE_SPACING_S = 2.5

# Cookies from a signed-in browser are yt-dlp's documented remedy for the
# "confirm you're not a bot" challenge. Off by default because reading the
# cookie store needs keychain access; set WSR_COOKIES_FROM=chrome to enable.
COOKIES_FROM = os.environ.get('WSR_COOKIES_FROM')

# A challenge is not a transient network error — retrying promptly makes it
# worse — so callers should back off hard when they see one.
class BotChallenge(RuntimeError):
    """YouTube refused the request pending human verification."""


def _looks_like_challenge(error: Exception) -> bool:
    text = str(error).lower()
    return 'not a bot' in text or 'sign in to confirm' in text


def _format_table(camera: str, force: bool = False) -> dict[str, str]:
    """{format_id: url} for a camera, cached until the URLs near expiry."""
    global _last_resolve
    video_id = CAMERAS.get(camera, camera)
    with _cache_lock:
        hit = _cache.get(video_id)
        if hit and not force and time.time() - hit[0] < CACHE_TTL_S:
            return hit[1]

    # yt-dlp needs a JavaScript runtime to solve YouTube's player
    # challenge, and enables only deno by default. Without one it warns
    # that extraction is deprecated and that formats may be missing —
    # which, on an eleven-hour unattended run, would mean discovering at
    # dusk that the day produced nothing. Node is already present.
    options: dict = {'quiet': True, 'js_runtimes': {'node': _node()}}
    if COOKIES_FROM:
        options['cookiesfrombrowser'] = (COOKIES_FROM,)

    # one resolution at a time, spaced apart, so a cold start trickles
    with _resolve_lock:
        wait = RESOLVE_SPACING_S - (time.time() - _last_resolve)
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.5))
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}', download=False)
        except Exception as error:
            if _looks_like_challenge(error):
                raise BotChallenge(
                    'YouTube is asking for human verification. Wait for it to '
                    'clear, or set WSR_COOKIES_FROM=chrome to pass cookies '
                    'from a signed-in browser.') from error
            raise
        finally:
            _last_resolve = time.time()

    table = {f['format_id']: f['url'] for f in info.get('formats', [])
             if f.get('url')}
    with _cache_lock:
        _cache[video_id] = (time.time(), table)
    return table


def resolve_hls_url(camera: str, format_spec: str = DEFAULT_FORMAT,
                    force: bool = False) -> str:
    """Resolve a camera to a stream URL, preferring cached format tables.

    format_spec is a '/'-separated preference list of format ids, e.g.
    '231/230/229' (480p, then 360p, then 240p).
    """
    table = _format_table(camera, force=force)
    for fmt in format_spec.split('/'):
        if fmt in table:
            return table[fmt]
    if not force:  # stale cache missing the format — re-extract once
        return resolve_hls_url(camera, format_spec, force=True)
    raise RuntimeError(f'no format from {format_spec} available for {camera}')


def open_stream(camera: str, format_spec: str = DEFAULT_FORMAT) -> cv2.VideoCapture:
    """Open a live camera as a cv2.VideoCapture for continuous reading."""
    return cv2.VideoCapture(resolve_hls_url(camera, format_spec))


def grab_frame(camera: str, format_spec: str = DEFAULT_FORMAT):
    """Grab a single BGR frame from a live camera (None on failure)."""
    cap = open_stream(camera, format_spec)
    try:
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


if __name__ == '__main__':
    for name in CAMERAS:
        frame = grab_frame(name)
        status = f'{frame.shape[1]}x{frame.shape[0]}' if frame is not None else 'FAILED'
        print(f'{name}: {status}')
