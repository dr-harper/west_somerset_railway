"""Can rails be found automatically, rather than traced by hand?

Three approaches, tested against the hand-traced rails at Bishops Lydeard:

  hough      classical edges plus a probabilistic Hough transform. Rails are
             long, high-contrast, near-parallel lines, which is exactly what
             Hough finds — but so are platform edges, fences, roof lines and
             cables.
  vanishing  Hough lines filtered to those converging on a common vanishing
             point, since real rails recede together and clutter does not.
  learned    where trains have actually been seen. A train can only travel on
             track, so accumulated detections trace the running lines without
             any notion of what a rail looks like — and unlike the other two,
             it cannot mistake a fence for a railway.

    python3 experiment_rail_detect.py
"""

import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
IMAGES = HERE / 'working_images'
W, H = 854, 480


def hough_lines(bgr: np.ndarray, min_length: int = 90) -> list:
    grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    grey = cv2.bilateralFilter(grey, 7, 60, 60)      # keep edges, drop ballast noise
    edges = cv2.Canny(grey, 45, 130)
    segments = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                               minLineLength=min_length, maxLineGap=18)
    if segments is None:
        return []
    # OpenCV returns (N,1,4) or (N,4) depending on build
    flat = segments.reshape(-1, 4)
    return [tuple(int(v) for v in row) for row in flat]


def line_angle(seg) -> float:
    x1, y1, x2, y2 = seg
    return np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180


def intersection(a, b):
    """Where two segments would meet if extended, or None if parallel."""
    (x1, y1, x2, y2), (x3, y3, x4, y4) = a, b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-6:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / d
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / d
    return px, py


def vanishing_point(segments) -> tuple | None:
    """Most agreed-upon meeting point of the segments, by simple voting."""
    votes = []
    for i, a in enumerate(segments):
        for b in segments[i + 1:]:
            if abs(line_angle(a) - line_angle(b)) < 4:
                continue                       # near-parallel: unstable
            point = intersection(a, b)
            if point and -2000 < point[0] < 2000 and -2000 < point[1] < 2000:
                votes.append(point)
    if len(votes) < 10:
        return None
    votes = np.array(votes)
    return tuple(np.median(votes, axis=0))


def converging(segments, vp, tolerance_deg: float = 6.0) -> list:
    """Segments that point at the vanishing point — as rails must."""
    keep = []
    for seg in segments:
        x1, y1, x2, y2 = seg
        mid = ((x1 + x2) / 2, (y1 + y2) / 2)
        to_vp = np.degrees(np.arctan2(vp[1] - mid[1], vp[0] - mid[0])) % 180
        if abs(to_vp - line_angle(seg)) < tolerance_deg:
            keep.append(seg)
    return keep


def traced_rails(camera: str) -> list:
    path = HERE / 'camera_tracks.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text()).get(camera, {})
    rails = []
    for track in data.get('tracks', []):
        for key in ('a', 'b'):
            points = track.get('rails', {}).get(key, [])
            if len(points) >= 2:
                rails.append(points)
    return rails


def distance_to_polyline(point, polyline) -> float:
    best = 1e9
    for a, b in zip(polyline, polyline[1:]):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, (
            (point[0] - ax) * dx + (point[1] - ay) * dy) / length))
        best = min(best, float(np.hypot(point[0] - (ax + t * dx),
                                        point[1] - (ay + t * dy))))
    return best


def score(segments, rails, tolerance: int = 18) -> float:
    """Share of detected segments that lie along a hand-traced rail."""
    if not segments or not rails:
        return 0.0
    hits = 0
    for x1, y1, x2, y2 in segments:
        mid = ((x1 + x2) / 2, (y1 + y2) / 2)
        if min(distance_to_polyline(mid, rail) for rail in rails) < tolerance:
            hits += 1
    return hits / len(segments)


def main() -> None:
    camera = 'bishops_lydeard'
    bgr = cv2.resize(cv2.imread(str(IMAGES / f'cam_{camera}.jpg')), (W, H))
    rails = traced_rails(camera)
    print(f'{len(rails)} hand-traced rails at {camera} as ground truth\n')

    raw = hough_lines(bgr)
    print(f'hough:      {len(raw):3d} segments, {score(raw, rails):.0%} on a real rail')

    vp = vanishing_point(raw)
    filtered = converging(raw, vp) if vp else []
    if vp:
        print(f'vanishing:  point at ({vp[0]:.0f}, {vp[1]:.0f}) — '
              f'{len(filtered):3d} segments converge, '
              f'{score(filtered, rails):.0%} on a real rail')

    canvas = bgr.copy()
    for x1, y1, x2, y2 in raw:
        cv2.line(canvas, (x1, y1), (x2, y2), (120, 120, 120), 1, cv2.LINE_AA)
    for x1, y1, x2, y2 in filtered:
        cv2.line(canvas, (x1, y1), (x2, y2), (60, 220, 255), 2, cv2.LINE_AA)
    for rail in rails:
        pts = np.array(rail, np.int32)
        cv2.polylines(canvas, [pts], False, (60, 220, 60), 2, cv2.LINE_AA)
    if vp and -500 < vp[0] < W + 500 and -500 < vp[1] < H + 500:
        cv2.circle(canvas, (int(vp[0]), int(vp[1])), 8, (200, 60, 220), 2)
    cv2.putText(canvas, 'grey: all Hough  yellow: converging  green: hand-traced',
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(IMAGES / 'experiment_rails.jpg'), canvas)
    print(f'\nrendered {IMAGES / "experiment_rails.jpg"}')


if __name__ == '__main__':
    main()
