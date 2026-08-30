"""Follow points on the vehicle itself — a window, a door, a panel edge.

Box tracking says where the detector thinks a train is; it does not say
whether the train moved. A box drawn round a standing rake wobbles across
it as the detector changes its mind about where the train ends, and the
box centre wanders with it. At Williton on 30/8 that produced 897px of
path for 179px of net displacement — a train that was standing still for
most of it, reported as moving.

Points stuck to the vehicle cannot do that. A window is either in the
same place next frame or it is not, and Lucas-Kanade says which by
looking at the pixels around it. That gives motion that is true by
construction, and with the rail gauge for scale it gives a speed in miles
per hour rather than pixels.

It needs frames close together, which is why this reads the dense clips
rather than the sampled ones: at 25fps a train at 20mph moves 0.36m per
frame and a window is still recognisably itself, where five seconds apart
it is somewhere else entirely.

    python3 feature_track.py captures/<clip>_dense.mp4
"""

import argparse
import math
from pathlib import Path

import cv2
import numpy as np

import track_geometry as tg

HERE = Path(__file__).parent

# Corners are picked inside the train only, and spread out, so the trails
# describe the vehicle rather than clustering on one bright window frame.
FEATURE_PARAMS = dict(maxCorners=60, qualityLevel=0.05, minDistance=14,
                      blockSize=7)
LK_PARAMS = dict(winSize=(21, 21), maxLevel=3,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                           30, 0.01))


def read_clip(path: Path) -> list:
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames


def train_box(detector, frame):
    found = detector.trains(frame, conf=0.35)
    if not found:
        return None
    _conf, box, _centre = max(
        found, key=lambda t: (t[1][2] - t[1][0]) * (t[1][3] - t[1][1]))
    return box


def follow(frames: list, box, start: int = 0):
    """Track corners from `start` for as long as they survive.

    Points are seeded only inside the detection box, so the trails belong
    to the train and not to the platform behind it.
    """
    x1, y1, x2, y2 = box
    grey = cv2.cvtColor(frames[start], cv2.COLOR_BGR2GRAY)
    mask = np.zeros(grey.shape, np.uint8)
    mask[y1:y2, x1:x2] = 255
    points = cv2.goodFeaturesToTrack(grey, mask=mask, **FEATURE_PARAMS)
    if points is None:
        return [], []

    trails = [[tuple(p[0])] for p in points]
    alive = [True] * len(points)
    previous = grey
    for index in range(start + 1, len(frames)):
        current = cv2.cvtColor(frames[index], cv2.COLOR_BGR2GRAY)
        moved, status, _err = cv2.calcOpticalFlowPyrLK(
            previous, current, points, None, **LK_PARAMS)
        if moved is None:
            break
        # A point that fails, or wanders outside the picture, is dropped
        # rather than allowed to drift onto the background.
        for i, (ok, point) in enumerate(zip(status.ravel(), moved)):
            if not alive[i]:
                continue
            x, y = point[0]
            if not ok or not (0 <= x < current.shape[1] and 0 <= y < current.shape[0]):
                alive[i] = False
                continue
            trails[i].append((float(x), float(y)))
        points = moved
        previous = current
    return trails, alive


# A point must run further than this to count as riding on the train.
# Seeding covers the whole detection box, which on a train filling the
# frame takes in the station building and the platform as well, so the
# points come in two populations and averaging across both is meaningless
# — it read a passing train at 0.4mph.
MOVING_PX = 25.0


def split_by_motion(trails: list) -> tuple[list, list]:
    """Points that rode the train, and points that stayed on the scenery."""
    moving, still = [], []
    for trail in trails:
        if len(trail) < 5:
            continue
        (moving if math.dist(trail[0], trail[-1]) >= MOVING_PX
         else still).append(trail)
    return moving, still


def speed_from(trails: list, camera: str, fps: float = 25.0) -> float | None:
    """Miles per hour, from how far the riding points ran and the gauge."""
    speeds = []
    for trail in trails:
        if len(trail) < 10:
            continue
        (x0, y0), (x1, y1) = trail[0], trail[-1]
        placed = tg.project(camera, ((x0 + x1) / 2, (y0 + y1) / 2))
        if not placed or not placed.get('metres_per_px'):
            continue
        metres = math.dist((x0, y0), (x1, y1)) * placed['metres_per_px']
        seconds = (len(trail) - 1) / fps
        if seconds > 0:
            speeds.append(metres / seconds * 2.23694)
    if not speeds:
        return None
    speeds.sort()
    return speeds[len(speeds) // 2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('clip')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--out', default='working_images/feature_track.jpg')
    args = parser.parse_args()

    path = Path(args.clip)
    frames = read_clip(path)
    if len(frames) < 10:
        print('clip too short')
        return
    camera = '_'.join(path.stem.split('_')[1:-1])

    from gala_watcher import SharedDetector
    detector = SharedDetector(str(HERE / 'yolo11s.pt'))
    box = train_box(detector, frames[args.start])
    if not box:
        print('no train detected in the starting frame')
        return

    trails, alive = follow(frames, box, args.start)
    if not trails:
        print('no features could be found on the train')
        return
    riding, scenery = split_by_motion(trails)
    travelled = sorted(math.dist(t[0], t[-1]) for t in riding)
    median = travelled[len(travelled) // 2] if travelled else 0.0
    speed = speed_from(riding, camera)

    print(f'{path.name}')
    print(f'  {len(frames)} frames, {len(trails)} points seeded in the box')
    print(f'  {len(riding)} rode the train, {len(scenery)} stayed on the scenery')
    if riding:
        print(f'  riding points travelled {travelled[0]:.0f}-{travelled[-1]:.0f} px, '
              f'median {median:.0f}')
    print(f'  speed {speed:.1f} mph' if speed else '  speed not measurable here')

    canvas = frames[args.start].copy()
    for trail in scenery:
        cv2.circle(canvas, (int(trail[0][0]), int(trail[0][1])), 2,
                   (120, 120, 120), -1)
    for trail in riding:
        pts = np.array(trail, np.int32)
        cv2.polylines(canvas, [pts], False, (60, 220, 255), 1, cv2.LINE_AA)
        cv2.circle(canvas, (int(trail[0][0]), int(trail[0][1])), 3,
                   (80, 240, 80), -1)
        cv2.circle(canvas, (int(trail[-1][0]), int(trail[-1][1])), 3,
                   (60, 60, 240), -1)
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(canvas,
                f'{len(riding)} points riding the train (grey = scenery), '
                f'median travel {median:.0f}px'
                + (f', {speed:.1f} mph' if speed else ''),
                (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                cv2.LINE_AA)
    cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f'  rendered {args.out}')


if __name__ == '__main__':
    main()
