"""Per-camera detection zones for the WSR live webcams.

Zones are polygons in 854x480 frame coordinates (the 480p HLS format used
by wsr_live_capture). Kinds:
  detect  - platform/running lines: a train here is a live movement or call
  approach- train entering here will reach the station shortly
  ignore  - sidings and stabled stock: permanently-parked vehicles

Usage:
  from detection_zones import ZONES, classify, draw_zones
  zone = classify('minehead_station', (cx, cy))   # zone name or None
"""

import cv2
import numpy as np

KIND_COLOURS = {          # BGR
    'detect': (80, 170, 60),
    'approach': (200, 140, 30),
    'ignore': (50, 50, 200),
}

# camera -> list of (name, kind, [(x, y), ...])
ZONES = {
    'minehead_station': [
        ('platform road (west)', 'detect',
         [(40, 480), (190, 480), (370, 195), (295, 180)]),
        ('platform road (east)', 'detect',
         [(505, 480), (700, 480), (462, 190), (415, 190)]),
        ('west sidings (stabled)', 'ignore',
         [(0, 480), (35, 480), (290, 178), (0, 178)]),
        ('shed roads (stabled)', 'ignore',
         [(705, 480), (854, 480), (854, 185), (465, 185)]),
    ],
    'minehead_seaward_crossing': [
        ('running line', 'detect',
         [(0, 480), (520, 480), (620, 212), (562, 196), (0, 398)]),
        ('goods siding (stabled)', 'ignore',
         [(0, 392), (0, 178), (540, 178), (585, 212), (515, 290)]),
        ('approach (station throat)', 'approach',
         [(600, 214), (720, 214), (720, 182), (600, 182)]),
    ],
    'blue_anchor': [
        ('platform roads', 'detect',
         [(355, 480), (760, 480), (485, 215), (408, 215)]),
        ('level crossing', 'approach',
         [(283, 232), (487, 232), (487, 193), (283, 193)]),
        ('approach (Dunster)', 'approach',
         [(315, 190), (468, 190), (432, 158), (348, 158)]),
    ],
    'watchet_visitor_centre': [
        ('running line (curve)', 'detect',
         [(578, 480), (795, 480), (790, 320), (700, 288), (612, 268), (562, 300)]),
        ('approach (Washford)', 'approach',
         [(590, 292), (658, 288), (648, 254), (588, 258)]),
    ],
    'crowcombe_heathfield': [
        ('platform roads', 'detect',
         [(150, 480), (854, 480), (854, 432), (262, 182), (182, 176)]),
        ('approach (Stogumber)', 'approach',
         [(120, 178), (200, 168), (192, 140), (128, 146)]),
    ],
    'bishops_lydeard': [
        ('platform roads', 'detect',
         [(0, 480), (385, 480), (530, 58), (415, 42), (0, 360)]),
        ('approach (yard / north)', 'approach',
         [(520, 52), (640, 88), (660, 48), (540, 26)]),
    ],
}


def classify(camera: str, point) -> str | None:
    """Return the zone name containing (x, y), preferring detect zones."""
    zones = sorted(ZONES.get(camera, []),
                   key=lambda z: {'detect': 0, 'approach': 1, 'ignore': 2}[z[1]])
    for name, _kind, poly in zones:
        contour = np.array(poly, dtype=np.int32)
        if cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0:
            return name
    return None


def draw_zones(frame, camera: str, alpha: float = 0.35):
    """Return a copy of the frame with that camera's zones overlaid."""
    out = frame.copy()
    overlay = frame.copy()
    for name, kind, poly in ZONES.get(camera, []):
        pts = np.array(poly, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], KIND_COLOURS[kind])
    out = cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0)
    for name, kind, poly in ZONES.get(camera, []):
        pts = np.array(poly, dtype=np.int32)
        cv2.polylines(out, [pts], True, KIND_COLOURS[kind], 2)
        cx, cy = pts.mean(axis=0).astype(int)
        label = f'{name} [{kind}]'
        size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        tx, ty = max(4, min(cx - size[0] // 2, 850 - size[0])), cy
        cv2.rectangle(out, (tx - 3, ty - size[1] - 4), (tx + size[0] + 3, ty + 4), (20, 20, 20), -1)
        cv2.putText(out, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (255, 255, 255), 1, cv2.LINE_AA)
    return out


if __name__ == '__main__':
    for camera in ZONES:
        frame = cv2.imread(f'cam_{camera}.jpg')
        if frame is None:
            continue
        cv2.imwrite(f'zones_{camera}.jpg', draw_zones(frame, camera))
        print(camera, 'rendered')
