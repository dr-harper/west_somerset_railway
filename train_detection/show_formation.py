"""Draw what the tracker holds, so a count can be checked against the picture."""
import sys
from collections import defaultdict

import cv2
import numpy as np
from ultralytics import YOLO

from tracking import Detection, TrainTracker, dedupe
from count_formation import read, NAMES

MIN_SEEN = 40
COL = {0: (90, 230, 90), 1: (220, 90, 220)}

clip = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else 'working_images/formation_track.jpg'
model = YOLO('runs/formation/weights/best.pt')
frames = read(clip)
trackers = {k: TrainTracker() for k in NAMES}
seen_at = defaultdict(dict)      # (cls, id) -> frame -> box
for i, frame in enumerate(frames):
    result = model.predict(frame, conf=0.45, verbose=False)[0]
    per = defaultdict(list)
    for b, c, s in zip(result.boxes.xyxy.cpu().numpy(),
                       result.boxes.cls.cpu().numpy(),
                       result.boxes.conf.cpu().numpy()):
        x1, y1, x2, y2 = [int(v) for v in b]
        per[int(c)].append(Detection(box=(x1, y1, x2, y2), conf=float(s),
                                     centre=((x1 + x2) // 2, (y1 + y2) // 2)))
    for cls, tracker in trackers.items():
        kept = dedupe(per.get(cls, []))
        for track in tracker.update(float(i), kept):
            cx, cy = track.path[-1][1], track.path[-1][2]
            match = min(kept, key=lambda d: (d.centre[0] - cx) ** 2 + (d.centre[1] - cy) ** 2)
            seen_at[(cls, track.track_id)][i] = match.box

real = {k: v for k, v in seen_at.items() if len(v) >= MIN_SEEN}
print(f'{len(frames)} frames | kept {sum(1 for k in real if k[0]==1)} loco, '
      f'{sum(1 for k in real if k[0]==0)} wagon (seen >= {MIN_SEEN} frames)')
for (cls, tid), boxes in sorted(real.items()):
    print(f'  {NAMES[cls]:<6} #{tid:<3} {len(boxes):>3} frames')

show = [0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1]
tiles = []
for i in show:
    canvas = frames[i].copy()
    for (cls, tid), boxes in sorted(real.items()):
        if i not in boxes:
            continue
        x1, y1, x2, y2 = boxes[i]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), COL[cls], 3)
        tag = f"{'LOCO' if cls else 'wagon'} #{tid}"
        cv2.putText(canvas, tag, (x1 + 4, max(16, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(canvas, tag, (x1 + 4, max(16, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COL[cls], 1, cv2.LINE_AA)
    tile = cv2.resize(canvas, (640, 360))
    bar = np.zeros((22, 640, 3), np.uint8)
    here = sum(1 for b in real.values() if i in b)
    cv2.putText(bar, f'frame {i} ({i // 25}s)  -  {here} vehicles held', (6, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    tiles.append(np.vstack([bar, tile]))
cv2.imwrite(out, np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])]),
            [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f'-> {out}')
