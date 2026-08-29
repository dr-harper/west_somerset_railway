"""Per-camera track geometry, traced as a PAIR of rails.

One centreline gives direction but no sense of scale: fifty pixels of
motion close to the camera is a very different distance from fifty pixels
near the horizon, so speed cannot be recovered and a curve still confuses
a single global direction vector.

Tracing BOTH rails fixes this, because their real separation is a known
constant. British standard gauge is 1.435 m, so wherever the rails sit
`g` pixels apart in the image, one pixel is 1.435/g metres THERE. That
gives, per camera and without any second sighting:

  direction   project motion onto the local tangent of the centreline,
              which is the midpoint curve between the rails;
  scale       metres per pixel at the train's own depth, from the local
              gauge, so perspective is handled rather than ignored;
  speed       pixel motion converted through that local scale;
  depth       the gauge shrinks with distance, so it doubles as a
              monotonic depth cue along the track.

Rails are multi-point polylines — the track curves, so two-point straight
lines will not do — ordered from the Bishops Lydeard end towards Minehead
and stored in camera_tracks.json in 854x480 image space. Trace them with
track_annotator.html.
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
TRACKS_PATH = HERE / 'camera_tracks.json'

STANDARD_GAUGE_M = 1.435
SAMPLES = 64          # resolution of the derived centreline


def load_tracks() -> dict:
    if not TRACKS_PATH.exists():
        return {}
    raw = json.loads(TRACKS_PATH.read_text())
    return {k: v for k, v in raw.items() if not k.startswith('_')}


TRACKS = load_tracks()


# --------------------------------------------------------------------------
# Polyline helpers
# --------------------------------------------------------------------------

def _cumulative(points):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    return lengths


def _point_at_fraction(points, fraction):
    """Point a given fraction along a polyline, by arc length."""
    lengths = _cumulative(points)
    total = lengths[-1]
    if total == 0:
        return points[0]
    target = max(0.0, min(1.0, fraction)) * total
    for i, (a, b) in enumerate(zip(points, points[1:])):
        if lengths[i + 1] >= target:
            span = lengths[i + 1] - lengths[i]
            t = (target - lengths[i]) / span if span else 0.0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return points[-1]


def _project_to_segment(point, a, b):
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.dist(point, a), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.dist(point, (ax + t * dx, ay + t * dy)), t


# --------------------------------------------------------------------------
# The rail pair
# --------------------------------------------------------------------------

def rails_of(camera: str):
    """Both rails as point lists, or None if the camera lacks a pair."""
    track = TRACKS.get(camera)
    if not track:
        return None
    rails = track.get('rails')
    if not rails or len(rails.get('a', [])) < 2 or len(rails.get('b', [])) < 2:
        return None
    return [tuple(p) for p in rails['a']], [tuple(p) for p in rails['b']]


def centreline(camera: str):
    """Midpoint curve between the rails, with the local gauge at each sample.

    Rails are paired by fraction of their own arc length, which keeps the
    pairing sensible even when one rail is traced with more points than
    the other or they start slightly out of step.
    """
    pair = rails_of(camera)
    if not pair:
        return None
    rail_a, rail_b = pair
    samples = []
    for i in range(SAMPLES + 1):
        fraction = i / SAMPLES
        pa = _point_at_fraction(rail_a, fraction)
        pb = _point_at_fraction(rail_b, fraction)
        samples.append({
            'point': ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2),
            'gauge_px': math.dist(pa, pb),
        })
    return samples


_CENTRELINE_CACHE: dict[str, list | None] = {}


def _cached_centreline(camera: str):
    if camera not in _CENTRELINE_CACHE:
        _CENTRELINE_CACHE[camera] = centreline(camera)
    return _CENTRELINE_CACHE[camera]


def project(camera: str, point) -> dict | None:
    """Where a point sits on the track, with the local scale there.

    Returns arc length along the centreline, the local tangent pointing
    towards Minehead, the gauge in pixels at that depth, and the metres
    per pixel it implies.
    """
    samples = _cached_centreline(camera)
    if not samples:
        return None
    curve = [s['point'] for s in samples]
    lengths = _cumulative(curve)

    best = None
    for i, (a, b) in enumerate(zip(curve, curve[1:])):
        distance, t = _project_to_segment(point, a, b)
        if best is None or distance < best['offset_px']:
            span = math.dist(a, b)
            tangent = ((b[0] - a[0]) / span, (b[1] - a[1]) / span) if span else (0.0, 0.0)
            gauge = samples[i]['gauge_px'] + t * (samples[i + 1]['gauge_px'] - samples[i]['gauge_px'])
            best = {
                'offset_px': distance,
                'arc_px': lengths[i] + t * span,
                'tangent_to_minehead': tangent,
                'gauge_px': gauge,
                'metres_per_px': STANDARD_GAUGE_M / gauge if gauge else None,
                'sample_index': i,
            }
    if best:
        total = lengths[-1]
        best['arc_normalised'] = best['arc_px'] / total if total else 0.0
        best['track_length_px'] = total
        # Tolerance scales with depth, and is generous vertically because a
        # detection box's centre sits above the rails by roughly half the
        # train's height — it is a filter for things beside the line, not a
        # precise fit.
        best['on_track'] = best['offset_px'] <= max(2.0 * best['gauge_px'], 20)
    return best


def direction_of_motion(camera: str, point, drift) -> str:
    """Northbound or southbound, from motion along the local tangent."""
    placed = project(camera, point)
    if not placed:
        return 'unclear'
    magnitude = math.hypot(*drift)
    if magnitude < 12:
        return 'unclear'
    tx, ty = placed['tangent_to_minehead']
    along = drift[0] * tx + drift[1] * ty
    if abs(along) < magnitude * 0.4:
        return 'unclear'      # mostly across the rails, not along them
    return 'northbound' if along > 0 else 'southbound'


def speed_mph(camera: str, path) -> float | None:
    """Speed from a centroid path of [seconds, x, y], using local scale.

    Each step is converted through the metres-per-pixel where that step
    happened, so a train accelerating away from the camera is not read as
    slowing down.
    """
    if not path or len(path) < 2:
        return None
    metres = 0.0
    for (t0, x0, y0), (t1, x1, y1) in zip(path, path[1:]):
        placed = project(camera, ((x0 + x1) / 2, (y0 + y1) / 2))
        if not placed or not placed['metres_per_px']:
            continue
        metres += math.dist((x0, y0), (x1, y1)) * placed['metres_per_px']
    seconds = path[-1][0] - path[0][0]
    if seconds <= 0:
        return None
    return metres / seconds * 2.23694


def vanishing_point(camera: str):
    """Where the two rails would converge, from their far-end segments.

    Only meaningful for the straight part of a view, so it is a diagnostic
    for how oblique the lens angle is rather than something the pipeline
    depends on — the gauge-based scale works on curves too.
    """
    pair = rails_of(camera)
    if not pair:
        return None
    (a1, a2), (b1, b2) = pair[0][-2:], pair[1][-2:]
    d1 = (a2[0] - a1[0], a2[1] - a1[1])
    d2 = (b2[0] - b1[0], b2[1] - b1[1])
    denominator = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denominator) < 1e-9:
        return None                      # rails parallel in image: no vanishing point
    t = ((b1[0] - a1[0]) * d2[1] - (b1[1] - a1[1]) * d2[0]) / denominator
    return (a1[0] + t * d1[0], a1[1] + t * d1[1])


def describe(camera: str) -> str:
    samples = _cached_centreline(camera)
    if not samples:
        return f'{camera}: no rail pair traced'
    gauges = [s['gauge_px'] for s in samples]
    near, far = max(gauges), min(gauges)
    length = _cumulative([s['point'] for s in samples])[-1]
    vp = vanishing_point(camera)
    return (f'{camera}: {length:.0f}px of track, gauge {far:.0f}-{near:.0f}px '
            f'({STANDARD_GAUGE_M / near:.3f}-{STANDARD_GAUGE_M / far:.3f} m/px), '
            f'vanishing point {"(%.0f, %.0f)" % vp if vp else "n/a"}')


if __name__ == '__main__':
    if not TRACKS:
        print('No tracks traced yet — run serve_annotator.py')
    for camera in TRACKS:
        print(describe(camera))
