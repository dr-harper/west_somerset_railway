"""Keep a recent still from every camera for the control room to show.

The streams themselves cannot be embedded — YouTube returns "Error 153,
video player configuration error" for these ids, a restriction set by
Railcam rather than a fault here — so the app cannot simply show the
live picture. It can show a recent frame, which is enough to answer the
question an operator actually has: is this camera pointing where I think,
and is anything happening at it.

Frames are written to a fixed name per camera and overwritten in place,
so the app can request the same URL and get whatever is current.

During a watcher run the watcher writes these itself from frames it has
already decoded, at no extra cost. This script is for the times it is not
running — or, as today, when it started before that was added.

    python3 live_snapshots.py --every 60
"""

import argparse
import time
from pathlib import Path

import cv2

from wsr_live_capture import CAMERAS, BotChallenge, grab_frame

HERE = Path(__file__).parent
OUT_DIR = HERE / 'working_images'
STALE_AFTER_S = 300


def snapshot_path(camera: str) -> Path:
    return OUT_DIR / f'live_{camera}.jpg'


def write_snapshot(camera: str, frame) -> bool:
    """Write via a temporary file so a reader never sees a half-written JPEG."""
    if frame is None:
        return False
    target = snapshot_path(camera)
    temp = target.with_suffix('.tmp.jpg')
    ok = cv2.imwrite(str(temp), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if ok:
        temp.replace(target)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--every', type=float, default=60,
                        help='seconds between rounds')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    backoff = 0.0

    while True:
        started = time.time()
        written = failed = 0
        for camera in CAMERAS:
            if backoff and time.time() < backoff:
                break
            try:
                frame = grab_frame(camera)
            except BotChallenge:
                # Same rule as the watcher: a challenge is a rate limit,
                # and retrying promptly deepens it.
                backoff = time.time() + 900
                print('bot challenge — pausing snapshots for 15 minutes')
                break
            except Exception:
                frame = None
            if write_snapshot(camera, frame):
                written += 1
            else:
                failed += 1
        print(f'{time.strftime("%H:%M:%S")} wrote {written}, failed {failed}, '
              f'took {time.time() - started:.0f}s')

        if args.once:
            return
        time.sleep(max(0.0, args.every - (time.time() - started)))


if __name__ == '__main__':
    main()
