"""Capture a dense burst of frames while a train is actually passing.

The watcher samples at 2Hz and its saved clips work out at roughly one
frame every five seconds of real time. A train at 20mph covers 45m in
that gap, so consecutive frames share nothing: optical flow finds no
match and there is no overlap to stitch. Anything that needs to follow
motion — measuring speed honestly, building a mosaic of a train longer
than the frame, counting vehicles as they pass — is impossible from what
is currently kept.

The frames exist. The HLS stream delivers about 25fps and the decoder
buffers them, so eighty consecutive reads come back instantly and cover
three seconds of real time — verified against the clock burnt into the
picture, which advanced 15:00:39 to 15:00:42 across one burst. The
watcher simply throws them away.

This runs alongside the watcher without disturbing it: poll one camera,
and when a train is both present and moving, pull a dense burst and keep
it for offline work.

    python3 burst_capture.py --camera blue_anchor --hours 3
"""

import argparse
import pickle
import time
from datetime import datetime
from pathlib import Path

import cv2

HERE = Path(__file__).parent
OUT_DIR = HERE / 'bursts'

BURST_FRAMES = 120          # about five seconds at stream rate
MOVING_THRESHOLD = 1.5      # mean absolute change across a short probe
PROBE_FRAMES = 25


def probe(cap) -> tuple[list, float]:
    """A short read, and how much the scene changed across it."""
    frames = []
    for _ in range(PROBE_FRAMES):
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    if len(frames) < 5:
        return frames, 0.0
    change = float(cv2.absdiff(frames[0], frames[-1]).mean())
    return frames, change


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera', default='blue_anchor')
    parser.add_argument('--hours', type=float, default=3.0)
    parser.add_argument('--every', type=float, default=20,
                        help='seconds between probes')
    args = parser.parse_args()

    from gala_watcher import SharedDetector
    from wsr_live_capture import resolve_hls_url

    OUT_DIR.mkdir(exist_ok=True)
    detector = SharedDetector(str(HERE / 'yolo11s.pt'))
    deadline = time.time() + args.hours * 3600
    captured = 0

    while time.time() < deadline:
        started = time.time()
        try:
            cap = cv2.VideoCapture(resolve_hls_url(args.camera))
            frames, change = probe(cap)
            if not frames:
                cap.release()
                time.sleep(args.every)
                continue

            # Both conditions: something moved, and it is a train. Either
            # alone gives crowds on a platform or a rake standing still.
            moving = change >= MOVING_THRESHOLD
            trains = detector.trains(frames[-1], conf=0.45)
            if moving and trains:
                burst = list(frames)
                while len(burst) < BURST_FRAMES:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    burst.append(frame)
                stamp = datetime.now().strftime('%Y%m%dT%H%M%S')
                path = OUT_DIR / f'{stamp}_{args.camera}.pkl'
                with path.open('wb') as handle:
                    pickle.dump({'camera': args.camera, 'at': stamp,
                                 'frames': burst}, handle)
                captured += 1
                print(f'{datetime.now():%H:%M:%S} captured {len(burst)} frames '
                      f'-> {path.name} (change {change:.1f})', flush=True)
            else:
                print(f'{datetime.now():%H:%M:%S} change {change:4.1f}, '
                      f'{"train" if trains else "no train"} — skipped', flush=True)
            cap.release()
        except Exception as error:
            print(f'{datetime.now():%H:%M:%S} {str(error)[:80]}', flush=True)
        time.sleep(max(0.0, args.every - (time.time() - started)))

    print(f'done, {captured} bursts captured')


if __name__ == '__main__':
    main()
