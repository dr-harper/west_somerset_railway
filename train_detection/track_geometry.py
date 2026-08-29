"""Per-camera track centrelines, and what they let us compute.

Zones answer "is a train roughly here". They cannot answer "which way is
it going" on a curve: at Watchet a northbound train drifts left across the
frame while a southbound one drifts down, so no single direction vector
fits. The track is a curve, and a blob plus one global vector is the wrong
model for it.

A track is instead a polyline traced along the rails in image space,
ordered from the Bishops Lydeard end towards Minehead. From that:

  direction   project motion onto the LOCAL tangent where the train is,
              so a curve is handled by construction;
  position    project the train onto the polyline to get arc length, i.e.
              how far along the visible track it stands;
  distance    with two anchors of known real-world position, arc length
              converts to miles, giving speed without a second camera;
  zones       a span of the polyline, rather than a hand-drawn blob.

Trace tracks with track_annotator.html; they are stored in
camera_tracks.json as image-space points at 854x480.
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
TRACKS_PATH = HERE / 'camera_tracks.json'


def load_tracks() -> dict:
    if not TRACKS_PATH.exists():
        return {}
    raw = json.loads(TRACKS_PATH.read_text())
    return {k: v for k, v in raw.items() if not k.startswith('_')}


TRACKS = load_tracks()


def _segments(points):
    return list(zip(points, points[1:]))


def _project_to_segment(point, a, b):
    """Closest point on segment a->b, as (distance, t along segment)."""
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.dist(point, a), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    closest = (ax + t * dx, ay + t * dy)
    return math.dist(point, closest), t


def project(camera: str, point) -> dict | None:
    """Where a point sits relative to a camera's track.

    Returns arc length along the track (pixels and normalised), the local
    tangent pointing towards Minehead, and how far off the track the point
    lies — which doubles as a sanity check that it is a train on the line
    rather than something beside it.
    """
    track = TRACKS.get(camera)
    if not track:
        return None
    points = [tuple(p) for p in track['points']]
    if len(points) < 2:
        return None

    best = None
    walked = 0.0
    for index, (a, b) in enumerate(_segments(points)):
        distance, t = _project_to_segment(point, a, b)
        span = math.dist(a, b)
        if best is None or distance < best['offset_px']:
            tangent = ((b[0] - a[0]) / span, (b[1] - a[1]) / span) if span else (0.0, 0.0)
            best = {
                'segment_index': index,
                'offset_px': distance,
                'arc_px': walked + t * span,
                'tangent_to_minehead': tangent,
            }
        walked += span
    if best:
        best['arc_normalised'] = best['arc_px'] / walked if walked else 0.0
        best['track_length_px'] = walked
    return best


def direction_of_motion(camera: str, point, drift) -> str:
    """Northbound or southbound, from motion projected on the local tangent.

    Handles curves by construction: the tangent is taken where the train
    actually is, not averaged over the whole frame.
    """
    placed = project(camera, point)
    if not placed:
        return 'unclear'
    magnitude = math.hypot(*drift)
    if magnitude < 12:
        return 'unclear'
    tx, ty = placed['tangent_to_minehead']
    along = drift[0] * tx + drift[1] * ty
    # motion mostly across the track is not travel along it
    if abs(along) < magnitude * 0.4:
        return 'unclear'
    return 'northbound' if along > 0 else 'southbound'


def arc_to_miles(camera: str, arc_px: float) -> float | None:
    """Convert arc length to miles using the track's two anchors."""
    track = TRACKS.get(camera)
    anchors = (track or {}).get('anchors')
    if not anchors or len(anchors) < 2:
        return None
    first, second = anchors[0], anchors[1]
    a1 = project(camera, tuple(first['point']))
    a2 = project(camera, tuple(second['point']))
    if not a1 or not a2:
        return None
    span_px = a2['arc_px'] - a1['arc_px']
    span_miles = second['miles'] - first['miles']
    if span_px == 0:
        return None
    return first['miles'] + (arc_px - a1['arc_px']) * span_miles / span_px


def describe(camera: str) -> str:
    track = TRACKS.get(camera)
    if not track:
        return f'{camera}: no track traced'
    points = track['points']
    length = sum(math.dist(a, b) for a, b in _segments([tuple(p) for p in points]))
    anchors = len(track.get('anchors', []))
    return (f'{camera}: {len(points)} points, {length:.0f}px of track, '
            f'{anchors} anchor(s)')


if __name__ == '__main__':
    if not TRACKS:
        print('No tracks traced yet — run track_annotator.html')
    for camera in TRACKS:
        print(describe(camera))
