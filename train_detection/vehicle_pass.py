"""Propose one box per vehicle inside every train we have already agreed on.

The train boxes in dataset/labels.json were reviewed by hand, so where a
train is is no longer in question — only how many vehicles it is made of.
That makes the proposals much better than they were when the rake had to
be guessed first: SAM is prompted only inside a box we both accepted, and
anything it returns that leaves that box is discarded.

Proposals, not labels. SAM merges distant coaches and occasionally
returns a window, so every box here is meant to be corrected in
label_review.html before it trains anything.

    python3 vehicle_pass.py --propose
    python3 vehicle_pass.py --queue
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
SOURCE = HERE / 'dataset'
OUT = HERE / 'dataset_vehicles'
SAMPLES = 9
MERGE_IOU = 0.35
MIN_AREA = 600


def overlap(a, b) -> float:
    return (a & b).sum() / max(1, (a | b).sum())


def points_in(box, shape, count=SAMPLES):
    """Points along the upper part of the train box, spread lengthways."""
    x1, y1, x2, y2 = box
    y = int(y1 + (y2 - y1) * 0.35)
    return [[int(x), y] for x in np.linspace(x1 + 8, x2 - 8, count)
            if 0 <= x < shape[1]]


def propose(image, box, sam):
    """Distinct regions SAM finds inside an agreed train box."""
    height, width = image.shape[:2]
    inside = np.zeros((height, width), bool)
    x1, y1, x2, y2 = [int(v) for v in box]
    inside[max(0, y1):y2, max(0, x1):x2] = True

    found = []
    for point in points_in((x1, y1, x2, y2), image.shape):
        result = sam.predict(image, points=[point], labels=[1], verbose=False)[0]
        if result.masks is None:
            continue
        for raw in result.masks.data.cpu().numpy():
            piece = cv2.resize(raw.astype(np.float32), (width, height)) > 0.5
            if piece.sum() < MIN_AREA:
                continue
            # Must belong to the train we agreed on, not the platform.
            if (piece & inside).sum() / max(1, piece.sum()) < 0.75:
                continue
            found.append(piece)

    merged = []
    for piece in sorted(found, key=lambda m: -m.sum()):
        if all(overlap(piece, kept) < MERGE_IOU for kept in merged):
            merged.append(piece)

    boxes = []
    span = x2 - x1
    for piece in merged:
        ys, xs = np.where(piece)
        if not len(xs):
            continue
        # A region reaching end to end is the whole train, which we
        # already have; anything shorter is a candidate vehicle.
        if xs.max() - xs.min() > 0.94 * span:
            continue
        boxes.append([float((xs.min() + xs.max()) / 2 / width),
                      float((ys.min() + ys.max()) / 2 / height),
                      float((xs.max() - xs.min()) / width),
                      float((ys.max() - ys.min()) / height)])
    return boxes


def run_propose() -> None:
    from ultralytics import SAM
    sam = SAM(str(HERE / 'mobile_sam.pt'))
    labels = json.loads((SOURCE / 'labels.json').read_text())
    OUT.mkdir(exist_ok=True)

    out = {}
    withtrain = {k: v for k, v in labels.items() if v['boxes']}
    print(f'{len(withtrain)} frames contain an agreed train')
    for n, (key, entry) in enumerate(sorted(withtrain.items()), 1):
        path = SOURCE / 'images' / entry['split'] / f'{key}.jpg'
        image = cv2.imread(str(path))
        if image is None:
            continue
        height, width = image.shape[:2]
        proposals = []
        for cx, cy, w, h in entry['boxes']:
            box = ((cx - w / 2) * width, (cy - h / 2) * height,
                   (cx + w / 2) * width, (cy + h / 2) * height)
            if box[2] - box[0] < 60 or box[3] - box[1] < 30:
                continue
            proposals += propose(image, box, sam)
        out[key] = {'camera': entry['camera'], 'split': entry['split'],
                    'image': f"dataset/images/{entry['split']}/{key}.jpg",
                    'trains': entry['boxes'], 'boxes': proposals}
        if n % 25 == 0:
            print(f'  {n}/{len(withtrain)} frames, '
                  f'{sum(len(v["boxes"]) for v in out.values())} proposals')
    (OUT / 'labels.json').write_text(json.dumps(out, indent=1))
    counts = defaultdict(int)
    for v in out.values():
        counts[len(v['boxes'])] += 1
    print(f'\n{len(out)} frames, {sum(len(v["boxes"]) for v in out.values())} '
          f'vehicle proposals')
    print('vehicles per frame:', dict(sorted(counts.items())))


def run_queue() -> None:
    """Order for review: the frames where the answer is least obvious first."""
    data = json.loads((OUT / 'labels.json').read_text())
    queue = []
    for key, entry in data.items():
        n = len(entry['boxes'])
        if n == 0:
            flag, note = 'none', 'No vehicles proposed — draw each one.'
        elif n == 1:
            flag, note = 'single', 'One vehicle proposed — is the rake longer?'
        else:
            flag, note = 'several', f'{n} proposed — split or merge as needed.'
        queue.append({'key': key, 'camera': entry['camera'],
                      'split': entry['split'], 'image': entry['image'],
                      'boxes': entry['boxes'], 'dropped': entry['trains'],
                      'flag': flag, 'note': note})
    order = {'none': 0, 'single': 1, 'several': 2}
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
