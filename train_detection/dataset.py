"""Assemble a training set from the frames the watcher has already saved.

The detector's failures are not subtle — a roof at 0.92, a bench, a café
sign — and they are all the same failure: COCO never showed the model a
West Somerset platform from a pole. Eleven fixed views is a small enough
world to simply teach it, and the material is already on disk.

Three decisions are worth stating, because each one is a way this could
quietly produce a good score and a bad model.

  Frames with no train are as valuable as frames with one. YOLO learns
  what is *not* an object from images that contain none, and the roof
  clip at 18:03 is three hundred frames of exactly the negative we need.
  Without them the model has never once been told the roof is a roof.

  Splitting must follow time, not chance. Two frames a second apart are
  the same picture; scattering them across train and validation lets the
  model memorise and then be tested on what it memorised. Here the split
  is by source clip, so no clip appears on both sides.

  Cameras must be balanced. Williton 2 has 277 stills and Blue Anchor 2
  has 40. Left alone the model would learn Williton very well and treat
  the rest as noise, which is the opposite of what is wanted.

One class, 'train'. Traction is a different question — what kind of
locomotive — and it is better answered on a clean masked crop than by
asking the detector to decide 'steam' versus 'diesel' at the same moment
it decides where the train is. The masks this produces make that crop
much better than a box does.

    python3 dataset.py --propose      # build it, with labels proposed
    python3 dataset.py --stats        # what would go in, without writing
"""

import argparse
import glob
import re
import json
import random
from collections import defaultdict
from pathlib import Path

import cv2

HERE = Path(__file__).parent
OUT = HERE / 'dataset'
PER_CAMERA = 150          # cap, so one busy camera cannot dominate
# Stills from 29/8 have the zone overlay burned into the pixels — a green
# wash over the running line and captions reading '[detect]'. The watcher
# writes them clean now, but training on the old ones would teach the
# model the annotation rather than the train. Colour statistics cannot
# separate them (a maroon coach scores as high as the wash), and the date
# separates them perfectly: 0 of 802 frames from 30/8 carry a caption bar,
# against 46 detectable ones from 29/8.
OVERLAID_BEFORE = '20260830' 
DENSE_EVERY = 25          # one frame a second; anything closer is a duplicate
TRAIN_CLASS = 6           # 'train' in COCO, for the proposing model
VAL_SHARE = 0.2


def camera_of(name: str) -> str:
    stem = name.rsplit('.', 1)[0]
    stem = re.sub(r'_f\d{4}$', '', stem)      # a dense frame's index
    for suffix in ('_key', '_hires', '_entry', '_dense'):
        stem = stem.replace(suffix, '')
    return '_'.join(stem.split('_')[1:])


def candidates() -> dict:
    """Frames worth labelling, grouped by camera.

    Each is (source, key, loader) where source is the clip or still it
    came from — the unit the split is made on, so that two frames from
    one passage never straddle train and validation.
    """
    found = defaultdict(list)
    for path in sorted(glob.glob(str(HERE / 'captures' / '*.jpg'))):
        name = Path(path).name
        if name[:8] < OVERLAID_BEFORE:
            continue
        found[camera_of(name)].append((path, Path(path).stem, ('still', path)))

    for clip in sorted(glob.glob(str(HERE / 'captures' / '*_dense.mp4'))):
        cap = cv2.VideoCapture(clip)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        if total <= 0:
            continue            # a clip the watcher was still writing
        camera = camera_of(Path(clip).name)
        for index in range(0, total, DENSE_EVERY):
            key = f'{Path(clip).stem}_f{index:04d}'
            found[camera].append((clip, key, ('clip', clip, index)))
    return found


def balanced(found: dict, cap: int, seed: int = 7) -> dict:
    """At most `cap` frames per camera, spread across its sources."""
    rng = random.Random(seed)
    chosen = {}
    for camera, items in found.items():
        by_source = defaultdict(list)
        for source, key, loader in items:
            by_source[source].append((key, loader))
        sources = sorted(by_source)
        picked = []
        # Round-robin over sources so one long clip cannot fill the quota.
        while len(picked) < cap and any(by_source[s] for s in sources):
            for source in sources:
                if not by_source[source] or len(picked) >= cap:
                    continue
                key, loader = by_source[source].pop(
                    rng.randrange(len(by_source[source])))
                picked.append((source, key, loader))
        chosen[camera] = picked
    return chosen


def split(picked: list, share: float, seed: int = 7) -> tuple[list, list]:
    """Hold out whole sources, never individual frames."""
    sources = sorted({source for source, _, _ in picked})
    rng = random.Random(seed)
    rng.shuffle(sources)
    held = set(sources[:max(1, int(len(sources) * share))])
    train = [p for p in picked if p[0] not in held]
    val = [p for p in picked if p[0] in held]
    return train, val


def load(loader):
    if loader[0] == 'still':
        return cv2.imread(loader[1])
    cap = cv2.VideoCapture(loader[1])
    cap.set(cv2.CAP_PROP_POS_FRAMES, loader[2])
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def propose(model, frame):
    """Boxes and masks the current model would draw, as a starting point.

    These are proposals for a person to correct, not labels. The roof will
    be among them, and rejecting it is precisely the point of the exercise.
    """
    result = model.predict(frame, conf=0.35, classes=[TRAIN_CLASS],
                           verbose=False)[0]
    if result.boxes is None or not len(result.boxes):
        return []
    height, width = frame.shape[:2]
    out = []
    for box, conf in zip(result.boxes.xyxy.cpu().numpy(),
                         result.boxes.conf.cpu().numpy()):
        x1, y1, x2, y2 = box
        out.append({
            'cx': float((x1 + x2) / 2 / width),
            'cy': float((y1 + y2) / 2 / height),
            'w': float((x2 - x1) / width),
            'h': float((y2 - y1) / height),
            'conf': float(conf),
            'accepted': None,       # a person decides; None means unreviewed
        })
    return out


def build(write: bool) -> None:
    found = candidates()
    chosen = balanced(found, PER_CAMERA)

    print(f"{'camera':<28} {'available':>10} {'chosen':>7} {'sources':>8}")
    for camera in sorted(chosen):
        sources = len({s for s, _, _ in chosen[camera]})
        print(f'{camera:<28} {len(found[camera]):>10} '
              f'{len(chosen[camera]):>7} {sources:>8}')
    total = sum(len(v) for v in chosen.values())
    print(f"{'':<28} {'':>10} {total:>7}\n")

    everything = [p for items in chosen.values() for p in items]
    train, val = split(everything, VAL_SHARE)
    print(f'{len(train)} training frames, {len(val)} validation frames, '
          f'held out by clip')
    if not write:
        return

    from ultralytics import YOLO
    model = YOLO(str(HERE / 'yolo11s-seg.pt'))
    manifest = {}
    for part, items in (('train', train), ('val', val)):
        images = OUT / 'images' / part
        images.mkdir(parents=True, exist_ok=True)
        for source, key, loader in items:
            frame = load(loader)
            if frame is None:
                continue
            cv2.imwrite(str(images / f'{key}.jpg'), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            manifest[key] = {
                'split': part,
                'camera': camera_of(key),
                'source': Path(source).name,
                'proposals': propose(model, frame),
            }
        print(f'  wrote {part}: {len(list(images.glob("*.jpg")))} images')

    (OUT / 'proposals.json').write_text(json.dumps(manifest, indent=1))
    (OUT / 'data.yaml').write_text(
        f'path: {OUT}\ntrain: images/train\nval: images/val\n'
        'names:\n  0: train\n')
    unreviewed = sum(len(m['proposals']) for m in manifest.values())
    empty = sum(1 for m in manifest.values() if not m['proposals'])
    print(f'\n{unreviewed} proposed boxes across {len(manifest)} frames '
          f'awaiting review')
    print(f'{empty} frames the model saw nothing in — negatives, if they '
          f'really are empty')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--propose', action='store_true',
                        help='write the dataset and propose labels')
    args = parser.parse_args()
    build(write=args.propose)


if __name__ == '__main__':
    main()
