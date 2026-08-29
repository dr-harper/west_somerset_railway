"""Capture frames from the WSR live webcams for train detection.

The West Somerset Railway cameras (run by Railcam UK) are public 24/7
YouTube Live streams on the "RailcamLive - WSR" channel. yt-dlp resolves
each stream to an HLS manifest that OpenCV can read directly, so frames
can be fed straight into a detection model.

Requires: pip install yt-dlp opencv-python
Note: yt-dlp warns it prefers a JavaScript runtime (deno) for YouTube
extraction; the HLS formats used here resolve fine without one today.

Usage:
    from wsr_live_capture import open_stream, grab_frame, CAMERAS

    frame = grab_frame('minehead_station')       # one BGR numpy array

    cap = open_stream('blue_anchor')             # or keep a stream open
    ok, frame = cap.read()
"""

import threading
import time

import cv2
import yt_dlp

# Verified live 28th August 2026
CAMERAS = {
    'minehead_station': 'k40FIAhyhjo',
    'minehead_seaward_crossing': 'cO1MFjvfKUE',
    'blue_anchor': 'oURn7l3gpr4',
    'watchet_visitor_centre': 'lHPtw6tKigc',
    'crowcombe_heathfield': 'ptn6Fnc5u08',
    'bishops_lydeard': 'hEa16bHxHMM',
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


def _format_table(camera: str, force: bool = False) -> dict[str, str]:
    """{format_id: url} for a camera, cached until the URLs near expiry."""
    video_id = CAMERAS.get(camera, camera)
    with _cache_lock:
        hit = _cache.get(video_id)
        if hit and not force and time.time() - hit[0] < CACHE_TTL_S:
            return hit[1]
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(
            f'https://www.youtube.com/watch?v={video_id}', download=False)
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
