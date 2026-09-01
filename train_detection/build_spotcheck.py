"""Render what a person should check, rather than all of it.

Three things can go wrong in a labelling pass, and only three are worth
anyone's evening:

  A box rejected that was really a train. The label is simply missing,
  which teaches the detector to ignore something it should find.

  A frame called empty that has a train in it. This is the expensive one:
  every pixel of that train becomes an example of 'not a train'.

  A box accepted that was not a train, which teaches the roof.

So the sheets are the ten rejects, the twenty-five negatives, and a
sample of accepts — not the three hundred boxes that were obvious.
"""
import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
DATA = HERE / 'dataset'
OUT = HERE / 'working_images' / 'spotcheck'


def tile(image, caption, colour=(255, 255, 255)):
    small = cv2.resize(image, (480, 270))
    bar = np.zeros((24, 480, 3), np.uint8)
    cv2.putText(bar, caption, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.44,
                colour, 1, cv2.LINE_AA)
    return np.vstack([bar, small])


def sheet(tiles, path, columns=4):
    if not tiles:
        return 0
    while len(tiles) % columns:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + columns]) for i in range(0, len(tiles), columns)]
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return len(tiles)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('*.jpg'):
        old.unlink()
    index = json.loads((DATA / 'review_index.json').read_text())
    labels = json.loads((DATA / 'labels.json').read_text())
    verdicts = json.loads((HERE / 'verdicts.json').read_text())

    rejected, accepted = [], []
    for number, verdict in verdicts.items():
        if number == 'exclude_frames':
            continue
        entry = index['proposals'][number]
        image = cv2.imread(str(DATA / 'images' / entry['split'] /
                               f"{entry['frame']}.jpg"))
        if image is None:
            continue
        height, width = image.shape[:2]
        cx, cy, bw, bh = entry['box']
        box = (int((cx - bw / 2) * width), int((cy - bh / 2) * height),
               int((cx + bw / 2) * width), int((cy + bh / 2) * height))
        colour = (80, 80, 240) if verdict == 'reject' else (90, 230, 90)
        cv2.rectangle(image, box[:2], box[2:], colour, max(2, width // 400))
        caption = (f"box {number}  {entry['camera']}  {verdict.upper()}  "
                   f"conf {entry['conf']:.2f}")
        (rejected if verdict == 'reject' else accepted).append(
            tile(image, caption, colour))

    negatives = []
    for key, entry in labels.items():
        if entry['boxes']:
            continue
        image = cv2.imread(str(DATA / 'images' / entry['split'] / f'{key}.jpg'))
        if image is not None:
            negatives.append(tile(image, f"{entry['camera']}  NEGATIVE - any train?",
                                  (60, 200, 255)))

    step = max(1, len(accepted) // 12)
    made = [
        ('rejects.jpg', rejected, 'Boxes I rejected - is any of these a real train?'),
        ('negatives.jpg', negatives, 'Frames labelled empty - does any contain a train?'),
        ('accepts.jpg', accepted[::step][:12], 'A sample of accepted boxes'),
    ]
    links = []
    for name, tiles, title in made:
        count = sheet(list(tiles), OUT / name)
        if count:
            links.append((name, title, count))
            print(f'  {name}: {count} tiles')

    body = ''.join(
        f'<section><h2>{title}</h2>'
        f'<p class="n">{count} shown</p>'
        f'<a href="spotcheck/{name}" target="_blank">'
        f'<img src="spotcheck/{name}" alt="{title}"></a></section>'
        for name, title, count in links)
    (HERE / 'working_images' / 'spotcheck.html').write_text(f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Label spot check</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 16px/1.5 system-ui, sans-serif; margin: 0; padding: 1rem 1rem 4rem;
        max-width: 900px; margin-inline: auto; }}
 h1 {{ font-size: 1.25rem; margin: 0 0 .25rem; }}
 .lead {{ opacity: .75; margin: 0 0 1.5rem; }}
 section {{ margin-bottom: 2.5rem; }}
 h2 {{ font-size: 1rem; margin: 0 0 .1rem; }}
 .n {{ margin: 0 0 .5rem; opacity: .6; font-size: .85rem; }}
 img {{ width: 100%; height: auto; border-radius: 6px;
        border: 1px solid color-mix(in srgb, currentColor 20%, transparent); }}
</style>
<h1>Label spot check</h1>
<p class="lead">243 frames labelled, 301 boxes, 25 negatives. Tap any sheet to
open it full size. What matters is whether a rejected box is really a train,
and whether a frame called empty has one in it.</p>
{body}
""")
    print('\n-> working_images/spotcheck.html')


if __name__ == '__main__':
    main()
