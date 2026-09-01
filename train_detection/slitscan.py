"""Rebuild a passing train from time, instead of from one frame.

Counting vehicles from a still fails on more than half the cameras
because the train does not fit in the frame — at Blue Anchor 2 and the
Watchet Visitor Centre a single coach fills it. But those cameras are
mounted close to the track, which makes them the best ones for this: a
moving train shows every part of itself through the same window, one
piece at a time, and the pieces can be laid back out in order.

The offsets come from phase correlation on the train's own pixels rather
than an assumed speed, so a train slowing into a platform still assembles
correctly. Sampling a narrow column rather than the whole frame avoids
the parallax that would smear a wide strip: only the part of the picture
level with the slit is ever used.

    python3 slitscan.py captures/<clip>_dense.mp4
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
SLIT = 8               # px sampled per frame, at the column below
MIN_RESPONSE = 0.03    # phase-correlation confidence worth trusting


def train_box(frames, model):
    """Where the train sits, from the frame with the biggest detection."""
    best = None
    for frame in frames[::20]:
        result = model.predict(frame, conf=0.4, verbose=False)[0]
        for box in result.boxes.xyxy.cpu().numpy():
            area = (box[2] - box[0]) * (box[3] - box[1])
            if best is None or area > best[0]:
                best = (area, [int(v) for v in box])
    return best[1] if best else None


def drift(frames, box):
    """Horizontal movement of the train's pixels, frame to frame."""
    x1, y1, x2, y2 = box
    out = [0.0]
    for i in range(len(frames) - 1):
        a = cv2.cvtColor(frames[i][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        b = cv2.cvtColor(frames[i + 1][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        if a.shape != b.shape or a.size == 0:
            out.append(out[-1])
            continue
        (dx, _dy), response = cv2.phaseCorrelate(np.float32(a), np.float32(b))
        out.append(out[-1] + (dx if response > MIN_RESPONSE else 0.0))
    return np.array(out)


def build(frames, box, offsets):
    """Lay out one slit per slit-width of travel, not one per frame.

    Placing every frame at its absolute offset leaves the reconstruction
    full of black bars: a train easing into a platform covers less than a
    slit-width in most frames and stands still in many, so most columns
    are never written and the few that are get overwritten. Resampling by
    distance instead of by time means a stationary train contributes
    nothing, which is right — it has no new part of itself to show.
    """
    x1, y1, x2, y2 = box
    centre = (x1 + x2) // 2
    half = max(1, SLIT // 2)
    travel = offsets - offsets[0]
    span = float(np.ptp(travel))
    if span < 40:
        return None, span

    # One direction only: the dominant one. A train that shunts back and
    # forth would otherwise write the same vehicles twice.
    forward = travel[-1] >= travel[0]
    columns = []
    last = travel[0]
    for frame, position in zip(frames, travel):
        moved = (position - last) if forward else (last - position)
        if moved < SLIT:
            continue
        column = frame[y1:y2, centre - half:centre + half]
        if column.shape[1] == 2 * half:
            columns.append(column)
        last = position
    if not columns:
        return None, span
    if forward:
        columns.reverse()      # later frames show track further back
    return np.hstack(columns), span


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('clip')
    parser.add_argument('--out', default='working_images/slitscan.jpg')
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.clip)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if len(frames) < 30:
        print('clip too short')
        return

    from ultralytics import YOLO
    model = YOLO(str(HERE / 'runs' / 'wsr' / 'weights' / 'best.pt'))
    box = train_box(frames, model)
    if not box:
        print('no train found')
        return
    offsets = drift(frames, box)
    strip, span = build(frames, box, offsets)
    print(f'{Path(args.clip).name}')
    print(f'  {len(frames)} frames, train box {box}')
    print(f'  train travelled {span:.0f}px through the slit')
    if strip is None:
        print('  too little movement to reconstruct anything')
        return
    print(f'  reconstruction {strip.shape[1]}x{strip.shape[0]}px '
          f'(frame is {frames[0].shape[1]}px wide)')
    cv2.imwrite(args.out, strip, [cv2.IMWRITE_JPEG_QUALITY, 94])
    print(f'  -> {args.out}')


if __name__ == '__main__':
    main()
