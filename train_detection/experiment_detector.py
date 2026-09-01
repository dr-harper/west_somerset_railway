"""Is COCO YOLO the right detector for eleven fixed railway cameras?

It is the obvious first choice and it got the project working, but it is
wrong in a specific way: COCO's 'train' class was learned from photographs
taken by people, and nothing in it resembles a station roof seen from a
pole at thirty degrees. The model has no way to know that the slate roof
at Williton is a roof, and it reports it as a train at 0.92.

Three candidate fixes were measured here rather than argued about.

  A background model. These cameras do not move, which is a prior the
  detector discards entirely. A temporal median over the day is what the
  camera sees when nothing is happening, and a train is what is not in it.

  Segmentation instead of boxes. A rake at an oblique angle fills a box
  that is largely platform and sky — between 16% and 54% of it here — and
  that surplus is what seeded optical flow onto buildings and what let one
  train be detected twice.

  Neither addresses the domain error, which is what the numbers below
  show. Only training on our own views can, and the material for that is
  already on disk.

    python3 experiment_detector.py background
    python3 experiment_detector.py masks
"""

import glob
import sys
from collections import defaultdict

import cv2
import numpy as np

# The Williton roof, measured from the tracks it generated. In the 854px
# views; the hires stills are twice this and are not comparable.
ROOF = (0, 160, 348, 474)
TRAIN_CLASS = 6         # 'train' in COCO


def backgrounds(limit: int = 40) -> dict:
    """What each camera looks like with nothing happening.

    The median rather than the mean: a train passing through a handful of
    frames does not shift the middle value, where it would drag an average
    towards itself and leave a ghost.
    """
    stills = defaultdict(list)
    for path in sorted(glob.glob('captures/*_key.jpg')):
        camera = '_'.join(path.split('/')[-1].replace('_key.jpg', '').split('_')[1:])
        stills[camera].append(path)

    models = {}
    for camera, paths in stills.items():
        spread = paths[::max(1, len(paths) // limit)][:limit]
        images = [cv2.imread(p) for p in spread]
        images = [i for i in images if i is not None]
        if len(images) < 8:
            continue
        shape = images[0].shape
        images = [i for i in images if i.shape == shape]
        models[camera] = np.median(np.stack(images), axis=0).astype(np.uint8)
    return models


def novelty(model, frame, box) -> float | None:
    """How unlike the empty scene this box is. Zero means identical."""
    if model is None or model.shape != frame.shape:
        return None
    x1, y1, x2, y2 = [max(0, v) for v in box]
    here = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    empty = cv2.cvtColor(model[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    if here.size == 0 or here.shape != empty.shape:
        return None
    return float(cv2.absdiff(here, empty).mean())


def frame_at(clip: str, index: int):
    cap = cv2.VideoCapture(clip)
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


# Hand-checked: every one of these was looked at before being labelled.
CASES = [
    ('williton_2 roof', 'williton_2',
     ('still', 'captures/20260830T173215_williton_2_key.jpg'), (0, 160, 348, 474), False),
    ('crowcombe bench', 'crowcombe_heathfield',
     ('clip', 'captures/20260830T175504_crowcombe_heathfield_dense.mp4', 375),
     (345, 212, 412, 243), False),
    ('blue anchor sign', 'blue_anchor',
     ('clip', 'captures/20260830T175444_blue_anchor_dense.mp4', 175),
     (174, 158, 244, 212), False),
    ('williton_2 steam loco', 'williton_2',
     ('still', 'captures/20260830T131320_williton_2_key.jpg'), (168, 136, 428, 360), True),
    ('williton_2 rake', 'williton_2',
     ('still', 'captures/20260830T131320_williton_2_key.jpg'), (409, 135, 853, 333), True),
    ('crowcombe train', 'crowcombe_heathfield',
     ('clip', 'captures/20260830T175504_crowcombe_heathfield_dense.mp4', 375),
     (143, 163, 208, 242), True),
    ('blue anchor train', 'blue_anchor',
     ('clip', 'captures/20260830T175444_blue_anchor_dense.mp4', 175),
     (313, 155, 593, 389), True),
    ('minehead moving loco', 'minehead_station',
     ('clip', 'captures/20260830T180712_minehead_station_dense.mp4', 0),
     (419, 186, 571, 326), True),
    ('minehead stabled rake', 'minehead_station',
     ('clip', 'captures/20260830T180712_minehead_station_dense.mp4', 0),
     (60, 150, 260, 260), True),
]


def load(source):
    return (cv2.imread(source[1]) if source[0] == 'still'
            else frame_at(source[1], source[2]))


def run_background() -> None:
    models = backgrounds()
    print(f'backgrounds for {len(models)} cameras\n')
    print(f"{'case':<24} {'real train':<11} {'novelty':>8}")
    for label, camera, source, box, real in CASES:
        image = load(source)
        if image is None:
            print(f'{label:<24} unreadable')
            continue
        score = novelty(models.get(camera), image, box)
        print(f'{label:<24} {str(real):<11} '
              f'{("%.1f" % score) if score is not None else "n/a":>8}')
    print('\nA train that has stood all day IS the background, so this '
          'cannot see stabled stock.')


def run_masks() -> None:
    """Are the roof detections a loose box, or does the model mean it?"""
    from ultralytics import YOLO
    from gala_watcher import SharedDetector

    boxes = SharedDetector('yolo11s.pt')
    masks = YOLO('yolo11s-seg.pt')

    def box_on_roof(box, share=0.6):
        x1, y1 = max(box[0], ROOF[0]), max(box[1], ROOF[1])
        x2, y2 = min(box[2], ROOF[2]), min(box[3], ROOF[3])
        overlap = max(0, x2 - x1) * max(0, y2 - y1)
        area = (box[2] - box[0]) * (box[3] - box[1])
        return bool(area) and overlap / area > share

    for clip in sorted(glob.glob('captures/*williton_2_dense.mp4')):
        cap = cv2.VideoCapture(clip)
        frames = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        cap.release()
        if not frames:
            continue
        sample = frames[::10]
        counts = dict(box_all=0, box_roof=0, mask_all=0, mask_roof=0, fill=[])
        for frame in sample:
            for _conf, box, _centre in boxes.trains(frame, conf=0.45):
                counts['box_all'] += 1
                counts['box_roof'] += box_on_roof(box)
            result = masks.predict(frame, conf=0.45, classes=[TRAIN_CLASS],
                                   verbose=False)[0]
            if result.masks is None:
                continue
            roof = np.zeros(frame.shape[:2], bool)
            roof[ROOF[1]:ROOF[3], ROOF[0]:ROOF[2]] = True
            for raw, box in zip(result.masks.data.cpu().numpy(),
                                result.boxes.xyxy.cpu().numpy()):
                mask = cv2.resize(raw.astype(np.float32),
                                  (frame.shape[1], frame.shape[0])) > 0.5
                counts['mask_all'] += 1
                counts['mask_roof'] += (mask & roof).sum() / max(1, mask.sum()) > 0.6
                x1, y1, x2, y2 = box
                counts['fill'].append(mask.sum() / max(1, (x2 - x1) * (y2 - y1)))
        fill = np.mean(counts['fill']) if counts['fill'] else 0
        print(f'{clip.split("/")[-1]}  ({len(sample)} frames)')
        print(f"   boxes {counts['box_all']:>4}, on the roof {counts['box_roof']:>4} "
              f"({counts['box_roof'] / max(1, counts['box_all']):.0%})")
        print(f"   masks {counts['mask_all']:>4}, on the roof {counts['mask_roof']:>4} "
              f"({counts['mask_roof'] / max(1, counts['mask_all']):.0%}), "
              f"box is {fill:.0%} train")


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'background'
    (run_masks if which == 'masks' else run_background)()
