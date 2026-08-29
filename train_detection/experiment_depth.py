"""Does monocular depth help us mask? An experiment across the scenes.

The claim under test is that depth cannot separate a platform from the
track beside it, because they are adjacent and at the same distance — and
that most of what depth reports is simply "how far up the frame this is",
which we already know for free.

Three measurements per camera:

  redundancy   correlation between predicted depth and image row. If depth
               is largely a function of height in frame, it adds little
               that the y coordinate does not already give.
  separation   depth either side of a platform/track boundary. A useful
               signal would show a step; a useless one shows a smooth ramp.
  zone contrast  depth inside detect zones versus ignore zones, which are
               the areas we already care about telling apart.

    python3 experiment_depth.py
"""

import json
from pathlib import Path

import cv2
import numpy as np
import torch

from detection_zones import ZONES

HERE = Path(__file__).parent
IMAGES = HERE / 'working_images'
OUT = HERE / 'working_images'


def load_model():
    import builtins
    builtins.input = lambda *a, **k: 'y'      # torch.hub trust prompt
    model = torch.hub.load('intel-isl/MiDaS', 'MiDaS_small', skip_validation=True)
    transform = torch.hub.load('intel-isl/MiDaS', 'transforms',
                               skip_validation=True).small_transform
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    return model.to(device).eval(), transform, device


def depth_of(model, transform, device, path: Path) -> tuple[np.ndarray, np.ndarray]:
    bgr = cv2.resize(cv2.imread(str(path)), (854, 480))
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        pred = model(transform(rgb).to(device))
        pred = torch.nn.functional.interpolate(
            pred.unsqueeze(1), size=rgb.shape[:2],
            mode='bicubic', align_corners=False).squeeze()
    return bgr, pred.cpu().numpy()


def redundancy(depth: np.ndarray) -> float:
    """How much of depth is explained by image row alone (Pearson r)."""
    rows = np.repeat(np.arange(depth.shape[0])[:, None], depth.shape[1], axis=1)
    return float(np.corrcoef(rows.ravel(), depth.ravel())[0, 1])


def zone_contrast(camera: str, depth: np.ndarray) -> dict:
    """Mean depth inside detect zones versus ignore zones."""
    stats = {}
    for kind in ('detect', 'ignore'):
        mask = np.zeros(depth.shape, np.uint8)
        found = False
        for _name, zone_kind, poly in ZONES.get(camera, []):
            if zone_kind == kind:
                cv2.fillPoly(mask, [np.array(poly, np.int32)], 255)
                found = True
        if found:
            values = depth[mask > 0]
            stats[kind] = (float(values.mean()), float(values.std()))
    return stats


def boundary_profile(depth: np.ndarray, row: int) -> np.ndarray:
    """Depth across one image row — a slice through platform and track."""
    return depth[row, :]


def main() -> None:
    model, transform, device = load_model()
    frames = sorted(IMAGES.glob('cam_*.jpg'))
    results = []

    for path in frames:
        camera = path.stem.replace('cam_', '')
        bgr, depth = depth_of(model, transform, device, path)
        entry = {
            'camera': camera,
            'row_correlation': round(redundancy(depth), 3),
            'zones': zone_contrast(camera, depth),
        }
        results.append(entry)

        # visual: frame, depth, and the two overlaid
        norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        coloured = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
        strip = np.hstack([cv2.resize(bgr, (427, 240)),
                           cv2.resize(coloured, (427, 240))])
        cv2.putText(strip, camera, (8, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(strip, f"depth~row r={entry['row_correlation']:+.2f}",
                    (435, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (255, 255, 255), 1, cv2.LINE_AA)
        entry['_strip'] = strip

    sheet = np.vstack([e.pop('_strip') for e in results])
    cv2.imwrite(str(OUT / 'experiment_depth.jpg'), sheet,
                [cv2.IMWRITE_JPEG_QUALITY, 85])

    print(f"{'camera':<28} {'depth~row r':>12}  {'detect mean':>12} {'ignore mean':>12}")
    for entry in results:
        detect = entry['zones'].get('detect')
        ignore = entry['zones'].get('ignore')
        print(f"{entry['camera']:<28} {entry['row_correlation']:>+12.3f}  "
              f"{detect[0] if detect else float('nan'):>12.0f} "
              f"{ignore[0] if ignore else float('nan'):>12.0f}")

    correlations = [abs(e['row_correlation']) for e in results]
    print(f"\nmean |correlation| between depth and image row: "
          f"{sum(correlations)/len(correlations):.3f}")
    (OUT / 'experiment_depth.json').write_text(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
