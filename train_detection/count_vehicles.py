"""Count vehicles by watching one place as the train goes past.

The reconstruction was solving a problem nobody had. Vehicles in a rake
are coupled together, so if they pass a fixed point one after another
they are one train — there is no need to rebuild the train to know that.
All that is needed is to watch a single spot and count what goes by.

So this reads one column of the picture, frame by frame, and records how
the bodyside there looks over time. A vehicle passing is a long steady
stretch; the gap between two vehicles is a brief dark notch. Count the
notches and you have the formation, with no speed, no offsets and no
stitching involved.

Only the bodyside band is read. The roof and the underframe run
continuously along a rake and would hide the very thing being counted.

    python3 count_vehicles.py captures/<clip>_dense.mp4
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent


def watch(frames, box, column=None):
    """How much of the full body height is dark at one column, per frame.

    Lightness alone counts windows. At a close-mounted camera a coach's
    windows pass the column many times more often than its ends do, and
    each one is the same bright-then-dark that a coupling gap makes — the
    first attempt read four windows as four vehicles.

    Height separates them. The gap between two vehicles is dark from roof
    to solebar; a window is dark only across the middle of the body. So
    what is recorded is the fraction of the body's height that is dark,
    which a window can never drive near 1.
    """
    x1, y1, x2, y2 = box
    at = column if column is not None else (x1 + x2) // 2
    trace = []
    for frame in frames:
        strip = frame[y1:y2, max(0, at - 3):at + 4]
        if strip.size == 0:
            trace.append(np.nan)
            continue
        grey = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY).mean(axis=1)
        # Dark relative to this column's own body, so a maroon coach and a
        # cream one are judged on the same terms.
        threshold = np.percentile(grey, 60) * 0.55
        trace.append(float((grey < threshold).mean()))
    return np.array(trace, dtype=np.float32)


def moving(frames, box, span=3, floor=0.4):
    """Whether the train's pixels are actually shifting, frame by frame.

    A standing train shows no vehicle ends at all, so anything counted
    while it is stopped is something else. The 17:53 clip sat still for
    its whole twenty seconds and was still credited with two vehicles.
    """
    x1, y1, x2, y2 = box
    out = np.zeros(len(frames), bool)
    for i in range(len(frames) - span):
        a = cv2.cvtColor(frames[i][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        b = cv2.cvtColor(frames[i + span][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        if a.shape != b.shape or a.size == 0:
            continue
        (dx, _dy), response = cv2.phaseCorrelate(np.float32(a), np.float32(b))
        out[i] = response > 0.03 and abs(dx) > floor
    return out


def count(trace, active=None, smooth=5, level=0.55):
    """Runs where the body is dark top-to-bottom — one per vehicle gap."""
    good = np.isfinite(trace)
    if good.sum() < 30:
        return [], trace
    filled = np.interp(np.arange(len(trace)), np.flatnonzero(good), trace[good])
    smoothed = np.convolve(filled, np.ones(smooth) / smooth, mode='same')
    dark = smoothed > level
    if active is not None:
        dark &= active[:len(dark)]
    gaps, start = [], None
    for i, on in enumerate(dark):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 2:              # a flicker is not a coupling
                gaps.append((start + i) // 2)
            start = None
    if start is not None and len(dark) - start >= 2:
        gaps.append((start + len(dark)) // 2)
    return gaps, smoothed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('clip')
    parser.add_argument('--out', default='working_images/vehicle_count.jpg')
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
    best = None
    for frame in frames[::20]:
        for box in model.predict(frame, conf=0.4, verbose=False)[0].boxes.xyxy.cpu().numpy():
            area = (box[2] - box[0]) * (box[3] - box[1])
            if best is None or area > best[0]:
                best = (area, [int(v) for v in box])
    if not best:
        print('no train found')
        return
    box = best[1]

    trace = watch(frames, box)
    active = moving(frames, box)
    notches, smoothed = count(trace, active)
    print(f'{Path(args.clip).name}')
    print(f'  watching column {(box[0] + box[2]) // 2} over {len(frames)} frames')
    moved = int(active.sum())
    print(f'  train moving in {moved} of {len(frames)} frames')
    if moved < 20:
        print('  train never moved — nothing passed, nothing to count')
    else:
        print(f'  {len(notches)} vehicle gaps seen -> {len(notches) + 1} vehicles passed')
    print(f'  at frames {list(map(int, notches))}')

    height = 260
    chart = np.full((height, len(trace), 3), 20, np.uint8)
    lo, hi = np.nanmin(smoothed), np.nanmax(smoothed)
    scaled = ((smoothed - lo) / max(1e-6, hi - lo) * (height - 30)).astype(int)
    for x in range(1, len(scaled)):
        cv2.line(chart, (x - 1, height - 15 - scaled[x - 1]),
                 (x, height - 15 - scaled[x]), (120, 230, 120), 1, cv2.LINE_AA)
    for n in notches:
        cv2.line(chart, (int(n), 0), (int(n), height), (60, 60, 240), 1)
    cv2.putText(chart, f'{len(notches) + 1} vehicles', (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(args.out, chart, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f'  -> {args.out}')


if __name__ == '__main__':
    main()
