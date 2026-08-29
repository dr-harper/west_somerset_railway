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


def resolve_hls_url(camera: str, format_spec: str = DEFAULT_FORMAT) -> str:
    """Resolve a camera name (or raw YouTube id) to its current HLS URL.

    HLS URLs expire after a few hours, so resolve rather than cache them.
    """
    video_id = CAMERAS.get(camera, camera)
    options = {'quiet': True, 'format': format_spec}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            f'https://www.youtube.com/watch?v={video_id}', download=False)
    return info['url']


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
