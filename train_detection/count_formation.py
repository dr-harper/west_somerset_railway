"""Count a train's formation from a video feed, by tracking what passes.

The count is a property of the feed, not of a frame. A wagon that drifts
off the edge has not stopped existing — it has been seen, it has an
identity, and it stays counted. So the formation is the number of
distinct track ids the feed ever held, not the most visible at once.

That is what makes this work on the cameras where a single coach fills
the frame: the train never has to fit in the picture, it only has to go
past.

One tracker per class rather than one for both. Wagons and locomotives
look nothing alike, and a shared tracker can hand a locomotive's identity
to the coach behind it as one leaves and the other arrives.

    python3 count_formation.py captures/<clip>_dense.mp4
"""

import argparse
from collections import defaultdict
from pathlib import Path

import cv2

from tracking import Detection, TrainTracker, dedupe

HERE = Path(__file__).parent
WEIGHTS = HERE / 'runs' / 'formation' / 'weights' / 'best.pt'
NAMES = {0: 'wagon', 1: 'loco'}


def read(clip):
    cap = cv2.VideoCapture(str(clip))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames


def formation(frames, model, conf=0.45, min_seen=3):
    """Distinct wagons and locomotives seen across the whole clip.

    A track seen only once or twice is not counted. Those are the flickers
    that inflate a formation — the departing train at Williton split into
    two ids for eight frames before settling, and counting every id ever
    issued would have made a four-coach rake into five.
    """
    trackers = {c: TrainTracker() for c in NAMES}
    for index, frame in enumerate(frames):
        result = model.predict(frame, conf=conf, verbose=False)[0]
        found = defaultdict(list)
        for box, cls, score in zip(result.boxes.xyxy.cpu().numpy(),
                                   result.boxes.cls.cpu().numpy(),
                                   result.boxes.conf.cpu().numpy()):
            x1, y1, x2, y2 = [int(v) for v in box]
            found[int(cls)].append(Detection(
                box=(x1, y1, x2, y2), conf=float(score),
                centre=((x1 + x2) // 2, (y1 + y2) // 2)))
        for cls, tracker in trackers.items():
            tracker.update(float(index), dedupe(found.get(cls, [])))

    counts, detail = {}, {}
    for cls, tracker in trackers.items():
        kept = [t for t in tracker.tracks.values() if len(t.path) >= min_seen]
        counts[NAMES[cls]] = len(kept)
        detail[NAMES[cls]] = sorted(
            (t.track_id, len(t.path), int(t.first_seen), int(t.last_seen))
            for t in kept)
    return counts, detail


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('clips', nargs='+')
    parser.add_argument('--conf', type=float, default=0.45)
    parser.add_argument('--min-seen', type=int, default=3)
    args = parser.parse_args()

    from ultralytics import YOLO
    model = YOLO(str(WEIGHTS))
    for clip in args.clips:
        frames = read(clip)
        if len(frames) < 20:
            print(f'{Path(clip).name}: too short')
            continue
        counts, detail = formation(frames, model, args.conf, args.min_seen)
        print(f'{Path(clip).name}  ({len(frames)} frames)')
        print(f"  formation: {counts['loco']} loco, {counts['wagon']} wagon")
        for kind in ('loco', 'wagon'):
            for tid, seen, first, last in detail[kind]:
                print(f'    {kind:<6} #{tid:<3} seen {seen:>3} frames, '
                      f'{first}-{last}')


if __name__ == '__main__':
    main()
