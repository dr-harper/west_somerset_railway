"""Write the vehicle labels out for training.

Two things are deliberate here.

Frames with no vehicle boxes are left out entirely rather than written as
empty label files. Every one of the 41 contains a train we both agreed
on, so calling it empty would teach the detector that a train is made of
nothing — the opposite of what it is being trained to see. Some were
frames SAM proposed nothing for and some were cleared by hand, and
neither is evidence of an empty train.

The images are symlinked into this set rather than copied. YOLO finds a
label by swapping 'images' for 'labels' in the image's path, so pointing
at dataset/images would send it to the *train* labels and quietly train
the wrong thing on the right pictures.
"""

import json
import os
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / 'dataset_vehicles'
SOURCE = HERE / 'dataset' / 'images'


def clamp(box):
    cx, cy, w, h = box
    x1, y1 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x2, y2 = min(1.0, cx + w / 2), min(1.0, cy + h / 2)
    return ((x1 + x2) / 2, (y1 + y2) / 2, max(0.0, x2 - x1), max(0.0, y2 - y1))


def main() -> None:
    labels = json.loads((OUT / 'labels.json').read_text())
    listed = defaultdict(list)
    skipped = 0
    for key, entry in labels.items():
        if not entry['boxes']:
            skipped += 1
            continue
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
        if not link.exists():
            os.symlink(os.path.relpath(source, images), link)

        out = OUT / 'labels' / split
        out.mkdir(parents=True, exist_ok=True)
        (out / f'{key}.txt').write_text('\n'.join(
            '0 ' + ' '.join(f'{v:.6f}' for v in clamp(b)) for b in entry['boxes']))
        listed[split].append(str(link.resolve()))

    for split, paths in listed.items():
        (OUT / f'{split}.txt').write_text('\n'.join(sorted(paths)))
        boxes = sum(len((OUT / 'labels' / split / (Path(p).stem + '.txt'))
                        .read_text().split('\n')) for p in paths)
        print(f'  {split}: {len(paths)} images, {boxes} vehicle boxes')
    (OUT / 'data.yaml').write_text(
        f'path: {OUT.resolve()}\ntrain: train.txt\nval: val.txt\n'
        'names:\n  0: vehicle\n')
    print(f'  {skipped} frames left out (train present but no vehicles marked)')
    print(f'  wrote {OUT / "data.yaml"}')


if __name__ == '__main__':
    main()
