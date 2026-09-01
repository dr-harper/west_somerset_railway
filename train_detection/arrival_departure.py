"""Say whether a train arrived, departed, or ran through.

A trend in speed is the wrong test — I tried it and a departure that was
already moving when the clip opened read as 'steady'. What actually
separates the cases is the ends: a train that arrives finishes at rest,
and one that departs begins at rest. Whether it was speeding up in
between does not matter and is not reliably measurable over twenty
seconds of a train easing along a platform.

Speed is measured on the train's own pixels rather than the box centre,
which wanders with the detector's opinion of where the train ends.

    python3 arrival_departure.py captures/<clip>_dense.mp4 ...
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
STILL = 0.06        # px/frame below which the train is not moving
EDGE = 60           # frames at each end that decide the verdict
# A train has to actually go somewhere. Peak speed alone called a standing
# rake an arrival — the 11:32 clip drifted two pixels in twenty seconds and
# noise was enough to clear a threshold on the maximum.
TRAVELLED = 25      # px over the clip, below which nothing really moved


def speed_trace(frames, box):
    x1, y1, x2, y2 = box
    out = []
    for i in range(len(frames) - 1):
        a = cv2.cvtColor(frames[i][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        b = cv2.cvtColor(frames[i + 1][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        if a.shape != b.shape or a.size == 0:
            out.append(0.0)
            continue
        (dx, _dy), response = cv2.phaseCorrelate(np.float32(a), np.float32(b))
        out.append(abs(dx) if response > 0.03 else 0.0)
    return np.convolve(out, np.ones(15) / 15, mode='same')


def verdict(speed):
    if len(speed) < 2 * EDGE:
        return 'too short', 0.0, 0.0
    start, end = float(speed[:EDGE].mean()), float(speed[-EDGE:].mean())
    if float(speed.sum()) < TRAVELLED:
        return 'standing', start, end
    if start < STILL and end >= STILL:
        return 'DEPARTURE', start, end
    if start >= STILL and end < STILL:
        return 'ARRIVAL', start, end
    if start < STILL and end < STILL:
        # Moved in the middle and is at rest at both ends: it came in and
        # stopped, which the clip caught whole.
        return 'ARRIVAL (whole stop)', start, end
    return 'running through', start, end


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('clips', nargs='+')
    args = parser.parse_args()
    from ultralytics import YOLO
    model = YOLO(str(HERE / 'runs' / 'formation' / 'weights' / 'best.pt'))
    for clip in args.clips:
        cap = cv2.VideoCapture(clip)
        frames = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        cap.release()
        name = Path(clip).stem.replace('_dense', '')
        if len(frames) < 60:
            print(f'{name:<44} too short')
            continue
        result = model.predict(frames[len(frames) // 2], conf=0.45, verbose=False)[0]
        if not len(result.boxes):
            print(f'{name:<44} no train')
            continue
        box = max(result.boxes.xyxy.cpu().numpy(),
                  key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        speed = speed_trace(frames, [int(v) for v in box])
        call, start, end = verdict(speed)
        print(f'{name:<44} start {start:.2f}  end {end:.2f}  -> {call}')


if __name__ == '__main__':
    main()
