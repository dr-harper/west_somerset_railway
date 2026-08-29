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

A camera usually sees MORE THAN ONE track: Blue Anchor is a passing loop
with two platform roads, Minehead has platform roads plus shed roads and
sidings, the Seaward Crossing has the running line alongside a goods
siding. Each is traced separately with its own rail pair, name and kind,
so a detection can be attributed to the track it is actually standing on
— which is what separates a movement from stabled stock, and tells you
which platform road a train at a loop has taken.

Rails are multi-point polylines — the track curves, so two-point straight
lines will not do — ordered from the Bishops Lydeard end towards Minehead
and stored in camera_tracks.json in 854x480 image space. Trace them with
track_annotator.html.
"""

import json
import math

import cv2
from pathlib import Path

HERE = Path(__file__).parent
TRACKS_PATH = HERE / 'camera_tracks.json'

STANDARD_GAUGE_M = 1.435
SAMPLES = 64          # resolution of the derived centreline

# Kinds a traced track can be. Only running lines and loops carry
# timetabled movements; stock on the others is stabled or being shunted.
RUNNING_KINDS = {'running', 'loop', 'platform'}

# Regions annotated alongside the rails. Kinds:
#   exclude   the motion gate must ignore this: platforms full of people,
#             roads, car parks, moving vegetation, sky. 95% of gates on
#             29/8 were false and this is the remedy.
#   platform  where passengers stand — a train stopped alongside one is
#             calling rather than passing, and a detection here that is
#             not on a track is probably a person.
#   occluder  something that hides the track (a signal post, a canopy) so
#             a train vanishing behind it does not end an episode.
REGION_KINDS = {'exclude', 'platform', 'occluder'}


def regions_of(camera: str, kind: str | None = None) -> list[dict]:
    """Annotated regions at a camera, optionally of one kind."""
    entry = TRACKS.get(camera) or {}
    out = []
    for region in entry.get('regions', []):
        points = region.get('points') or []
        if len(points) < 3:
            continue          # a polygon needs three corners
        if kind and region.get('kind') != kind:
            continue
        out.append({
            'name': region.get('name', region.get('kind', 'region')),
            'kind': region.get('kind', 'exclude'),
            'points': [tuple(p) for p in points],
        })
    return out


def exclusion_mask(camera: str, width: int, height: int):
    """Binary mask of everything the motion gate should ignore.

    Combines polygon 'exclude' regions with cells painted on the coarse
    grid. Painting is the practical route — an exclusion is 'that whole
    corner of the view', not a shape worth drawing corner by corner.
    """
    import numpy as np

    mask = np.zeros((height, width), np.uint8)
    scale_x, scale_y = width / 854, height / 480
    for region in regions_of(camera, 'exclude'):
        pts = np.array([[p[0] * scale_x, p[1] * scale_y]
                        for p in region['points']], np.int32)
        cv2.fillPoly(mask, [pts], 255)

    painted = (TRACKS.get(camera) or {}).get('mask_cells') or {}
    cells = painted.get('cells') or []
    if cells:
        grid_w, grid_h = painted.get('grid', [32, 18])
        cell_w, cell_h = width / grid_w, height / grid_h
        for cell in cells:
            col, row = cell % grid_w, cell // grid_w
            cv2.rectangle(mask,
                          (int(col * cell_w), int(row * cell_h)),
                          (int((col + 1) * cell_w), int((row + 1) * cell_h)),
                          255, -1)
    return mask


def corridor_mask(camera: str, width: int, height: int,
                  gauges: float = 3.0):
    """Where a train can appear, taken from the traced rails.

    The hand-drawn detect zones do this for the six original cameras, but
    the rails describe the same corridor more precisely and are already
    traced. Width follows the local gauge, so the band narrows into the
    distance exactly as the track does — a fixed pixel width would be far
    too wide at the vanishing point and too narrow in the foreground.
    """
    import numpy as np

    mask = np.zeros((height, width), np.uint8)
    scale_x, scale_y = width / 854, height / 480
    for track in tracks_of(camera):
        samples = _cached_centreline(camera, track['name']) or []
        for near, far in zip(samples, samples[1:]):
            a = (int(near['point'][0] * scale_x), int(near['point'][1] * scale_y))
            b = (int(far['point'][0] * scale_x), int(far['point'][1] * scale_y))
            gauge = (near['gauge_px'] + far['gauge_px']) / 2 * scale_x
            cv2.line(mask, a, b, 255, max(2, int(gauge * gauges)))
    return mask


def in_region(camera: str, point, kind: str) -> str | None:
    """Name of the region of that kind containing the point, if any."""
    px, py = point
    for region in regions_of(camera, kind):
        poly = region['points']
        inside = False
        j = len(poly) - 1
        for i, (xi, yi) in enumerate(poly):
            xj, yj = poly[j]
            if (yi > py) != (yj > py) and \
                    px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-9) + xi:
                inside = not inside
            j = i
        if inside:
            return region['name']
    return None


# Below this the two rails are too close to measure against: a few pixels
# of tracing error becomes a large fraction of the gauge, so the implied
# scale swings wildly. Rails traced right up to their vanishing point hit
# this, and any scale derived there is meaningless rather than merely
# imprecise — so it is withheld instead of reported.
MIN_RELIABLE_GAUGE_PX = 14.0


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

def tracks_of(camera: str) -> list[dict]:
    """Every traced track at a camera, newest format or legacy single pair."""
    entry = TRACKS.get(camera)
    if not entry:
        return []
    if 'tracks' in entry:
        candidates = entry['tracks']
    elif 'rails' in entry:      # legacy: one unnamed running line
        candidates = [{'name': 'running line', 'kind': 'running',
                       'rails': entry['rails']}]
    else:
        return []
    out = []
    for track in candidates:
        rails = track.get('rails') or {}
        if len(rails.get('a', [])) >= 2 and len(rails.get('b', [])) >= 2:
            out.append({
                'name': track.get('name', 'track'),
                'kind': track.get('kind', 'running'),
                'rails': ([tuple(p) for p in rails['a']],
                          [tuple(p) for p in rails['b']]),
            })
    return out


def rails_of(camera: str, name: str | None = None):
    """One track's rail pair; the first traced track if none is named."""
    for track in tracks_of(camera):
        if name is None or track['name'] == name:
            return track['rails']
    return None


def centreline(camera: str, name: str | None = None):
    """Midpoint curve between a track's rails, with local gauge per sample.

    Rails are paired by fraction of their own arc length, which keeps the
    pairing sensible even when one rail is traced with more points than
    the other or they start slightly out of step.
    """
    pair = rails_of(camera, name)
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


_CENTRELINE_CACHE: dict[tuple[str, str | None], list | None] = {}


def _cached_centreline(camera: str, name: str | None = None):
    key = (camera, name)
    if key not in _CENTRELINE_CACHE:
        _CENTRELINE_CACHE[key] = centreline(camera, name)
    return _CENTRELINE_CACHE[key]


def project_onto(camera: str, name: str, point) -> dict | None:
    """Where a point sits on one named track."""
    samples = _cached_centreline(camera, name)
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
            reliable = gauge >= MIN_RELIABLE_GAUGE_PX
            best = {
                'track': name,
                'offset_px': distance,
                'arc_px': lengths[i] + t * span,
                'tangent_to_minehead': tangent,
                'gauge_px': gauge,
                # withheld where the rails are too close to measure against
                'metres_per_px': (STANDARD_GAUGE_M / gauge) if reliable else None,
                'scale_reliable': reliable,
                'sample_index': i,
            }
    if best:
        total = lengths[-1]
        best['arc_normalised'] = best['arc_px'] / total if total else 0.0
        best['track_length_px'] = total
        # Offset in gauges, not pixels: a siding in the distance sits far
        # fewer pixels from its neighbour than one in the foreground, so
        # comparing raw pixels would always favour whatever is nearest.
        best['offset_gauges'] = best['offset_px'] / best['gauge_px'] if best['gauge_px'] else 999
        # Generous vertically, because a detection box's centre sits above
        # the rails by roughly half the train's height.
        best['on_track'] = best['offset_gauges'] <= 2.0
    return best


def project(camera: str, point) -> dict | None:
    """Attribute a point to the most likely track at this camera.

    Returns that track's geometry with its name and kind, plus whether it
    is a running line — the distinction between a movement and stabled
    stock — and how clearly it beat the runner-up.
    """
    candidates = []
    for track in tracks_of(camera):
        placed = project_onto(camera, track['name'], point)
        if placed:
            placed['kind'] = track['kind']
            placed['is_running_line'] = track['kind'] in RUNNING_KINDS
            candidates.append(placed)
    if not candidates:
        return None
    candidates.sort(key=lambda c: c['offset_gauges'])
    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    best['alternatives'] = [
        {'track': c['track'], 'offset_gauges': round(c['offset_gauges'], 2)}
        for c in candidates[1:]
    ]
    # If two tracks fit almost equally the attribution is a guess, and a
    # caller deciding "movement or stabled" should know that.
    best['ambiguous'] = bool(
        runner_up and runner_up['offset_gauges'] - best['offset_gauges'] < 0.5)
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


def speed_mph(camera: str, path, track: str | None = None) -> float | None:
    """Speed from a centroid path of [seconds, x, y], using local scale.

    Each step is converted through the metres-per-pixel where that step
    happened, so a train accelerating away from the camera is not read as
    slowing down. Steps in the far distance, where the rails are too close
    together to give a trustworthy scale, are skipped — and if that leaves
    nothing measurable, no speed is reported rather than a wrong one.
    """
    if not path or len(path) < 2:
        return None
    metres = 0.0
    measured = 0.0
    for (t0, x0, y0), (t1, x1, y1) in zip(path, path[1:]):
        midpoint = ((x0 + x1) / 2, (y0 + y1) / 2)
        placed = (project_onto(camera, track, midpoint) if track
                  else project(camera, midpoint))
        if not placed or not placed['metres_per_px']:
            continue
        metres += math.dist((x0, y0), (x1, y1)) * placed['metres_per_px']
        measured += t1 - t0
    if measured <= 0:
        return None
    return metres / measured * 2.23694


def vanishing_point(camera: str, name: str | None = None):
    """Where the two rails would converge, from their far-end segments.

    Only meaningful for the straight part of a view, so it is a diagnostic
    for how oblique the lens angle is rather than something the pipeline
    depends on — the gauge-based scale works on curves too.
    """
    pair = rails_of(camera, name)
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
    tracks = tracks_of(camera)
    if not tracks:
        return f'{camera}: no track traced'
    lines = [f'{camera}: {len(tracks)} track(s)']
    for track in tracks:
        samples = _cached_centreline(camera, track['name'])
        gauges = [s['gauge_px'] for s in samples]
        near, far = max(gauges), min(gauges)
        length = _cumulative([s['point'] for s in samples])[-1]
        usable = [s for s in samples if s['gauge_px'] >= MIN_RELIABLE_GAUGE_PX]
        share = len(usable) / len(samples)
        line = (f"    {track['name']} [{track['kind']}]: {length:.0f}px, "
                f'gauge {far:.0f}-{near:.0f}px')
        if usable:
            best = max(s['gauge_px'] for s in usable)
            worst = min(s['gauge_px'] for s in usable)
            line += (f' ({STANDARD_GAUGE_M / best:.3f}-'
                     f'{STANDARD_GAUGE_M / worst:.3f} m/px over '
                     f'{share:.0%} of its length)')
        if share < 0.95:
            line += (f'\n        WARNING: rails converge below '
                     f'{MIN_RELIABLE_GAUGE_PX:.0f}px over the far '
                     f'{1 - share:.0%} — trim the trace short of the '
                     f'vanishing point')
        lines.append(line)
    return '\n'.join(lines)


if __name__ == '__main__':
    if not TRACKS:
        print('No tracks traced yet — run serve_annotator.py')
    for camera in TRACKS:
        print(describe(camera))
