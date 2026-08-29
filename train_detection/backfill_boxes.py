"""Recover detection boxes for stills captured before they were recorded.

Until now the watcher drew zones and boxes into the saved keyframe. That
made the annotation permanent — it could not be lifted to read a running
number underneath, and any later reader saw the drawing as part of the
photograph. The watcher now writes the frame clean and records the boxes
beside it, but the 29/8 run predates that.

The hi-res stills were always saved clean, so the boxes can be recovered
by running the detector over them once. Coordinates are stored against
the image they belong to, at that image's own resolution, so the overlay
scales correctly whichever still the UI shows.

    python3 backfill_boxes.py [--limit 10] [--dry-run]
"""

import argparse
import json
from pathlib import Path

import cv2

HERE = Path(__file__).parent
CAPTURES = HERE / 'captures'
EPISODES = HERE / 'episodes.jsonl'


def boxes_for(detector, path: Path, camera: str) -> dict | None:
    frame = cv2.imread(str(path))
    if frame is None:
        return None
    height, width = frame.shape[:2]
    detections = []
    for confidence, box, centre in detector.trains(frame, conf=0.35):
        from detection_zones import ZONES, classify
        zone = classify(camera, centre) if camera in ZONES else None
        detections.append({'box': [int(v) for v in box],
                           'conf': confidence, 'zone': zone})
    return {'width': width, 'height': height, 'detections': detections}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    episodes = [json.loads(line) for line in EPISODES.read_text().splitlines()
                if line.strip()]
    todo = [e for e in episodes if not e.get('boxes')]
    if args.limit:
        todo = todo[:args.limit]
    print(f'{len(episodes)} episodes, {len(todo)} without box data')
    if not todo:
        return

    from gala_watcher import SharedDetector
    detector = SharedDetector(str(HERE / 'yolo11s.pt'))

    found = blank = 0
    for index, episode in enumerate(todo, 1):
        # The hi-res still was always written clean, so it is the one worth
        # detecting against; a burnt-in keyframe would have the old overlay
        # inside the very box being recovered.
        name = episode.get('hires')
        if not name or not (CAPTURES / name).exists():
            continue
        result = boxes_for(detector, CAPTURES / name, episode['camera'])
        if result is None:
            continue
        episode.setdefault('boxes', {})[name] = result
        if result['detections']:
            found += 1
        else:
            blank += 1
        print(f"[{index}/{len(todo)}] {episode['t_enter']} {episode['camera']}: "
              f"{len(result['detections'])} box(es)")

    print(f'\n{found} stills with boxes, {blank} where the detector found '
          f'nothing at 1080p')

    if args.dry_run:
        print('dry run — episodes.jsonl untouched')
        return
    EPISODES.write_text(
        '\n'.join(json.dumps(e) for e in episodes) + '\n')
    print(f'updated {EPISODES.name}')


if __name__ == '__main__':
    main()
