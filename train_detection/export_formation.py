"""Combine the two passes into one two-class training set.

The images are COPIED, not symlinked. YOLO finds a label by swapping
'images' for 'labels' in the image's path, and it resolves a symlink
first — so a linked image under dataset_formation/images sent it to
dataset/labels, which holds the whole-train boxes. Two models trained
that way before it was noticed: both reported a single class, drew boxes
spanning entire trains, and found no locomotives at all, while validating
at 0.99 mAP against the wrong labels. A copy cannot be redirected.

Class 0 is a wagon — hauled stock. Class 1 is a locomotive. They were
labelled in separate passes over the same frames, which is what makes
combining them safe: every frame here was looked at for both, so an
absent locomotive means there wasn't one, not that nobody checked.

A frame with a train but neither a wagon nor a locomotive marked is left
out. It cannot be true — a train is made of something — so it is either
an unreviewed frame or a mistake, and as training data it would teach
that a train is background.
"""

import json
import os
import shutil
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / 'dataset_formation'
SOURCE = HERE / 'dataset' / 'images'


def clamp(box):
    cx, cy, w, h = box
    x1, y1 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x2, y2 = min(1.0, cx + w / 2), min(1.0, cy + h / 2)
    return ((x1 + x2) / 2, (y1 + y2) / 2, max(0.0, x2 - x1), max(0.0, y2 - y1))


def main() -> None:
    wagons = json.loads((HERE / 'dataset_vehicles' / 'labels.json').read_text())
    locos = json.loads((HERE / 'dataset_locos' / 'labels.json').read_text())

    listed = defaultdict(list)
    counts = defaultdict(int)
    empty = 0
    for key in sorted(set(wagons) | set(locos)):
        wagon_boxes = wagons.get(key, {}).get('boxes', [])
        loco_boxes = locos.get(key, {}).get('boxes', [])
        if not wagon_boxes and not loco_boxes:
            empty += 1
            continue
        entry = wagons.get(key) or locos.get(key)
        split = entry['split']
        source = SOURCE / split / f'{key}.jpg'
        if not source.exists():
            found = next((s for s in ('train', 'val')
                          if (SOURCE / s / f'{key}.jpg').exists()), None)
            if not found:
                continue
            split, source = found, SOURCE / found / f'{key}.jpg'

        images = OUT / 'images' / split
        images.mkdir(parents=True, exist_ok=True)
        link = images / f'{key}.jpg'
        if link.is_symlink():
            link.unlink()
        if not link.exists():
            shutil.copy2(source, link)

        rows = ([f"0 " + ' '.join(f'{v:.6f}' for v in clamp(b)) for b in wagon_boxes]
                + [f"1 " + ' '.join(f'{v:.6f}' for v in clamp(b)) for b in loco_boxes])
        out = OUT / 'labels' / split
        out.mkdir(parents=True, exist_ok=True)
        (out / f'{key}.txt').write_text('\n'.join(rows))
        listed[split].append(str(link.resolve()))
        counts['wagon'] += len(wagon_boxes)
        counts['loco'] += len(loco_boxes)

    for split, paths in listed.items():
        (OUT / f'{split}.txt').write_text('\n'.join(sorted(paths)))
        print(f'  {split}: {len(paths)} images')
    (OUT / 'data.yaml').write_text(
        f'path: {OUT.resolve()}\ntrain: train.txt\nval: val.txt\n'
        'names:\n  0: wagon\n  1: loco\n')
    print(f"  {counts['wagon']} wagon boxes, {counts['loco']} loco boxes")
    print(f'  {empty} frames left out (train present, nothing marked)')


if __name__ == '__main__':
    main()
