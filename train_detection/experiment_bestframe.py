"""Pick the frame that shows the whole train, not whichever one we saved.

The stills kept per episode are captured at fixed moments — when the gate
opened, four seconds later, and on rising confidence — and none of those
is chosen for showing the locomotive. Several of 30/8's stills caught the
middle of a rake with the engine already past, and two caught an empty
platform because the entry frame had been backfilled to before the train
arrived.

The clip has the whole passage in it at 2fps. Sampling it and scoring
each frame gives a better still for nothing but a little inference, and
the score is a useful fact in itself: a detection box clear of the frame
edges means the whole train is inside the picture, which is exactly the
condition under which its length can be measured.

    python3 experiment_bestframe.py [--limit 6]
"""

import argparse
import json
from pathlib import Path

import cv2

HERE = Path(__file__).parent
CAPTURES = HERE / 'captures'

EDGE_PX = 6          # nearer than this to a border counts as touching it
SAMPLES = 10         # frames to look at per clip


def score(box, width: int, height: int) -> tuple[bool, float]:
    """Whether the train is wholly in frame, and how much of it we see."""
    x1, y1, x2, y2 = box
    contained = (x1 > EDGE_PX and y1 > EDGE_PX
                 and x2 < width - EDGE_PX and y2 < height - EDGE_PX)
    area = (x2 - x1) * (y2 - y1) / (width * height)
    return contained, area


def best_frame(detector, clip_path: Path, samples: int = SAMPLES):
    """The frame whose detection is most completely inside the picture.

    Prefers a train wholly in view over a larger one running off the edge:
    a box against the border says nothing about where the train ends.
    """
    cap = cv2.VideoCapture(str(clip_path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        return None

    step = max(1, len(frames) // samples)
    best = None
    for index in range(0, len(frames), step):
        frame = frames[index]
        height, width = frame.shape[:2]
        for confidence, box, _centre in detector.trains(frame, conf=0.35):
            contained, area = score(box, width, height)
            key = (contained, area, confidence)
            if best is None or key > best['key']:
                best = {'key': key, 'frame': frame, 'index': index,
                        'box': box, 'conf': confidence,
                        'contained': contained, 'area': area,
                        'of': len(frames)}
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=6)
    parser.add_argument('--date', default='2026-08-30')
    args = parser.parse_args()

    episodes = [json.loads(line) for line
                in (HERE / 'episodes.jsonl').read_text().splitlines() if line.strip()]
    episodes = [e for e in episodes
                if e['t_enter'].startswith(args.date) and e.get('clip')
                and (CAPTURES / e['clip']).exists()
                and (e.get('peak_conf') or 0) >= 0.85]

    from gala_watcher import SharedDetector
    detector = SharedDetector(str(HERE / 'yolo11s.pt'))

    print(f"{'time':<9} {'camera':<24} {'frames':>7} {'best':>6} "
          f"{'whole train':>12} {'area':>6}")
    kept = []
    for episode in episodes[:args.limit]:
        found = best_frame(detector, CAPTURES / episode['clip'])
        if not found:
            print(f"{episode['t_enter'][11:19]:<9} {episode['camera'][:23]:<24} "
                  f"no detection in the clip")
            continue
        print(f"{episode['t_enter'][11:19]:<9} {episode['camera'][:23]:<24} "
              f"{found['of']:>7} {found['index']:>6} "
              f"{('yes' if found['contained'] else 'runs off edge'):>12} "
              f"{found['area']:>5.0%}")
        kept.append((episode, found))

    # Render the saved still against the chosen frame, so the difference
    # can be judged rather than asserted.
    tiles = []
    for episode, found in kept:
        saved_name = episode.get('entry_frame') or episode.get('hires')
        saved = cv2.imread(str(CAPTURES / saved_name)) if saved_name else None
        chosen = found['frame'].copy()
        x1, y1, x2, y2 = found['box']
        cv2.rectangle(chosen, (x1, y1), (x2, y2), (60, 220, 255), 2)
        pair = []
        for image, label in ((saved, 'saved still'), (chosen, 'chosen from clip')):
            if image is None:
                continue
            tile = cv2.resize(image, (427, 240))
            cv2.rectangle(tile, (0, 0), (427, 18), (0, 0, 0), -1)
            cv2.putText(tile, f"{episode['t_enter'][11:16]} {label}", (4, 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1,
                        cv2.LINE_AA)
            pair.append(tile)
        if len(pair) == 2:
            import numpy as np
            tiles.append(np.hstack(pair))
    if tiles:
        import numpy as np
        out = HERE / 'working_images' / 'bestframe.jpg'
        cv2.imwrite(str(out), np.vstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f'\nrendered {out}')


if __name__ == '__main__':
    main()
