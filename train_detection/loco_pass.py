"""Propose the locomotive: the part of a train that is not a wagon.

The wagon pass already says which parts of each agreed train are hauled
stock. Whatever is left inside the train box and is big enough to matter
is, on a railway, almost always the thing pulling it. So the proposals
here are the residue — train minus wagons — rather than a fresh search,
which makes them far better than prompting a segmenter blind.

Two cases this cannot resolve and a person must:

  A multiple unit has no separate locomotive. The DMUs on this line are
  powered cars in a rake, so the residue may be nothing at all, and that
  is the right answer rather than a miss.

  A light engine has no wagons, so the whole train box is residue. That
  is exactly the case worth having, and it looks identical to a failure
  of the wagon pass until someone looks.

    python3 loco_pass.py --propose
    python3 loco_pass.py --queue
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
WAGONS = HERE / 'dataset_vehicles'
OUT = HERE / 'dataset_locos'
MIN_SIDE = 0.02        # of frame width; smaller is noise
MIN_SHARE = 0.35       # of the train box's height, as for wagons


def to_pixels(box, width, height):
    cx, cy, w, h = box
    return (int((cx - w / 2) * width), int((cy - h / 2) * height),
            int((cx + w / 2) * width), int((cy + h / 2) * height))


def residue(train, wagons, shape):
    """Parts of the train box no wagon covers."""
    height, width = shape[:2]
    x1, y1, x2, y2 = to_pixels(train, width, height)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    if x2 - x1 < 20 or y2 - y1 < 20:
        return []
    canvas = np.ones((y2 - y1, x2 - x1), np.uint8)
    for wagon in wagons:
        wx1, wy1, wx2, wy2 = to_pixels(wagon, width, height)
        canvas[max(0, wy1 - y1):max(0, wy2 - y1),
               max(0, wx1 - x1):max(0, wx2 - x1)] = 0
    # Close small holes so a gangway or a gap between two wagon boxes does
    # not read as a locomotive.
    canvas = cv2.morphologyEx(canvas, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    count, _labels, stats, _c = cv2.connectedComponentsWithStats(canvas, 8)
    out = []
    for i in range(1, count):
        bx, by, bw, bh, area = stats[i]
        if bw < MIN_SIDE * width or bh < MIN_SIDE * height:
            continue
        if bh < MIN_SHARE * (y2 - y1):
            continue
        if area < 0.25 * bw * bh:
            continue
        out.append([float((x1 + bx + bw / 2) / width),
                    float((y1 + by + bh / 2) / height),
                    float(bw / width), float(bh / height)])
    return out


def run_propose() -> None:
    wagons = json.loads((WAGONS / 'labels.json').read_text())
    OUT.mkdir(exist_ok=True)
    out = {}
    for key, entry in sorted(wagons.items()):
        image = cv2.imread(entry['image'])
        if image is None:
            continue
        proposals = []
        for train in entry['trains']:
            proposals += residue(train, entry['boxes'], image.shape)
        out[key] = {'camera': entry['camera'], 'split': entry['split'],
                    'image': entry['image'], 'trains': entry['trains'],
                    'wagons': entry['boxes'], 'boxes': proposals}
    (OUT / 'labels.json').write_text(json.dumps(out, indent=1))
    counts = defaultdict(int)
    for v in out.values():
        counts[len(v['boxes'])] += 1
    print(f'{len(out)} frames, {sum(len(v["boxes"]) for v in out.values())} '
          f'locomotive proposals')
    print('proposals per frame:', dict(sorted(counts.items())))


def run_queue() -> None:
    data = json.loads((OUT / 'labels.json').read_text())
    queue = []
    for key, entry in data.items():
        n, w = len(entry['boxes']), len(entry['wagons'])
        if not w:
            flag, note = 'nowagons', 'No wagons here — light engine, or a unit?'
        elif n == 0:
            flag, note = 'none', 'Nothing left over — draw the loco, or skip if a unit.'
        elif n == 1:
            flag, note = 'one', 'One candidate — is it the locomotive?'
        else:
            flag, note = 'several', f'{n} candidates — keep only real locomotives.'
        queue.append({'key': key, 'camera': entry['camera'],
                      'split': entry['split'], 'image': entry['image'],
                      'boxes': entry['boxes'],
                      'dropped': entry['wagons'],
                      'flag': flag, 'note': note})
    order = {'nowagons': 0, 'one': 1, 'several': 2, 'none': 3}
    queue.sort(key=lambda q: (order[q['flag']], q['camera'], q['key']))
    (OUT / 'review_queue.json').write_text(json.dumps(queue, indent=1))
    counts = defaultdict(int)
    for item in queue:
        counts[item['flag']] += 1
    print(f'{len(queue)} frames queued: ' +
          ', '.join(f'{v} {k}' for k, v in sorted(counts.items())))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--propose', action='store_true')
    parser.add_argument('--queue', action='store_true')
    args = parser.parse_args()
    if args.propose:
        run_propose()
    elif args.queue:
        run_queue()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
