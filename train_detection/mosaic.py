"""Stitch a passing train into one picture, longer than the frame.

Every tag that failed — length, formation, light engine — failed for the
same reason: the train does not fit in the frame, so a single still can
say nothing about where it ends. A train passing a fixed camera solves
that for free if the frames are dense enough. Each frame shows a
different part of the train through the same window; laid side by side at
the right offsets they reconstruct the whole thing.

The offsets come from phase correlation on the train's own region rather
than from an assumed speed, so an accelerating or braking train still
assembles correctly. The camera must be static for the run of frames
used: these are PTZ cameras and a zoom moves every pixel, which is
measured separately and used to cut the burst into static runs.

    python3 mosaic.py bursts/<file>.pkl
"""

import argparse
import pickle
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent

# A background patch used to tell camera movement from train movement.
BACKGROUND_PATCH = (0, 60, 300, 200)
CAMERA_STILL_PX = 1.0


def camera_shift(a, b, patch=BACKGROUND_PATCH) -> float:
    x1, y1, x2, y2 = patch
    left = cv2.cvtColor(a[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY).astype(np.float32)
    right = cv2.cvtColor(b[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), _ = cv2.phaseCorrelate(left, right)
    return abs(dx) + abs(dy)


def static_runs(frames: list, min_length: int = 20) -> list[tuple[int, int]]:
    """Spans of frames over which the camera did not move."""
    runs, start = [], 0
    for index in range(len(frames) - 1):
        if camera_shift(frames[index], frames[index + 1]) >= CAMERA_STILL_PX:
            if index - start >= min_length:
                runs.append((start, index))
            start = index + 1
    if len(frames) - 1 - start >= min_length:
        runs.append((start, len(frames) - 1))
    return runs


def train_shifts(frames: list, box) -> list[float]:
    """Horizontal shift of the train between consecutive frames."""
    x1, y1, x2, y2 = box
    shifts = []
    for a, b in zip(frames, frames[1:]):
        left = cv2.cvtColor(a[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY).astype(np.float32)
        right = cv2.cvtColor(b[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY).astype(np.float32)
        (dx, _), _ = cv2.phaseCorrelate(left, right)
        shifts.append(dx)
    return shifts


def build(frames: list, box, shifts: list[float]) -> np.ndarray | None:
    """Lay each frame's strip of the train at its cumulative offset.

    Only the band the train occupies is taken, and only the width it
    actually advanced, so each column of the mosaic comes from the frame
    in which it was closest to the middle of the picture — where the lens
    distorts least and the train is sharpest.
    """
    x1, y1, x2, y2 = box
    if not shifts:
        return None
    direction = -1 if np.median(shifts) < 0 else 1
    positions = np.cumsum([0] + [abs(s) for s in shifts])
    span = int(positions[-1]) + (x2 - x1)
    if span <= 0 or span > 40000:
        return None
    canvas = np.zeros((y2 - y1, span, 3), np.uint8)
    for index, frame in enumerate(frames):
        offset = int(positions[index])
        strip = frame[y1:y2, x1:x2]
        # How much new train appeared since the last frame, rounded up and
        # then widened by a pixel: truncating a 5.98px shift to 5 leaves a
        # one-pixel gap per frame, which prints as black banding across the
        # whole mosaic. Overlapping instead costs nothing — neighbouring
        # frames agree about the overlap.
        raw = abs(shifts[index]) if index < len(shifts) else strip.shape[1]
        advance = max(1, min(int(np.ceil(raw)) + 1, strip.shape[1]))
        take = strip[:, :advance] if direction < 0 else strip[:, -advance:]
        end = min(span, offset + advance)
        if end > offset:
            canvas[:, offset:end] = take[:, :end - offset]
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('burst')
    parser.add_argument('--out', default='working_images/mosaic.jpg')
    args = parser.parse_args()

    with open(args.burst, 'rb') as handle:
        data = pickle.load(handle)
    frames = data['frames']
    runs = static_runs(frames)
    print(f"{data.get('camera')}: {len(frames)} frames, "
          f"{len(runs)} static run(s) {runs}")
    if not runs:
        print('no run long enough with the camera still')
        return

    start, end = max(runs, key=lambda r: r[1] - r[0])
    segment = frames[start:end + 1]

    from gala_watcher import SharedDetector
    detector = SharedDetector(str(HERE / 'yolo11s.pt'))
    found = detector.trains(segment[0], conf=0.4)
    if not found:
        print('no train detected in the static run')
        return
    _confidence, box, _centre = max(
        found, key=lambda t: (t[1][2] - t[1][0]) * (t[1][3] - t[1][1]))

    shifts = train_shifts(segment, box)
    median = float(np.median(shifts))
    print(f'train shift {median:+.2f} px/frame (median), '
          f'total {sum(abs(s) for s in shifts):.0f} px over {len(segment)} frames')
    if abs(median) < 0.5:
        print('the train is not moving — nothing to stitch')
        return

    canvas = build(segment, box, shifts)
    if canvas is None:
        print('could not build a canvas')
        return
    cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f'wrote {args.out}  ({canvas.shape[1]}x{canvas.shape[0]})')


if __name__ == '__main__':
    main()
