"""Prove the new capture path against one live stream, briefly.

Everything else about the ring is tested against files and synthetic
frames. What that cannot show is whether a reader thread keeps up with
HLS, which is the only thing the change actually has to do tomorrow
morning.

One camera, not eleven. Cold-starting the whole line alongside a running
watcher is what drew a bot challenge on 29/8 and left six cameras blind
for half an hour.

    python3 live_ring_check.py --camera blue_anchor_2 --seconds 30
"""

import argparse
import time

from frame_ring import FrameRing, StreamReader
from gala_watcher import RING_SECONDS
from wsr_live_capture import resolve_hls_url

import cv2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera', default='blue_anchor_2')
    parser.add_argument('--seconds', type=float, default=30.0)
    args = parser.parse_args()

    print(f'resolving {args.camera} ...')
    try:
        url = resolve_hls_url(args.camera)
    except Exception as error:
        print(f'  could not resolve: {error}')
        return
    if not url:
        print('  no stream url')
        return
    print('  resolved')

    # The window the watcher will actually run, not a test value.
    ring = FrameRing(seconds=RING_SECONDS)
    errors = []
    reader = StreamReader(args.camera, ring,
                          lambda: cv2.VideoCapture(url),
                          on_error=errors.append)
    started = time.time()
    reader.start()
    try:
        while time.time() - started < args.seconds:
            time.sleep(2.0)
            held = len(ring)
            print(f'  {time.time() - started:>5.1f}s  {held:>4} frames  '
                  f'{ring.rate():>5.1f} fps  span {ring.span():>5.1f}s  '
                  f'{ring.nbytes() / 1e6:>5.1f} MB')
    finally:
        reader.stop()
        time.sleep(0.3)

    elapsed = time.time() - started
    print(f'\n{ring.added} frames captured in {elapsed:.0f}s '
          f'= {ring.added / elapsed:.1f} fps sustained')
    print(f'ring holds {len(ring)} frames over {ring.span():.1f}s, '
          f'{ring.nbytes() / 1e6:.1f} MB')
    print(f'measured rate for the writer: {ring.rate():.1f} fps')
    print(f'reconnects: {reader.reconnects}, errors: {len(errors)}')
    for error in errors[:3]:
        print(f'  {str(error)[:120]}')

    # The number that matters: the run-up a clip would open with,
    # against twelve frames yesterday.
    run_up = ring.tail(RING_SECONDS)
    if run_up:
        print(f'\nrun-up available: {len(run_up)} frames over '
              f'{run_up[-1][0] - run_up[0][0]:.1f}s')


if __name__ == '__main__':
    main()
