"""Does the fine-tuned model still see a train on the Williton roof?

mAP is not the question. The question is the one that broke the pipeline:
Williton 2 logged 91 episodes on 30/8 where its partner camera logged 20,
because a slate roof reads as a carriage side at 0.92 confidence.

So this counts detections on the roof, per model, over the clips where
the fault is worst — including 18:03, twenty seconds of rain with no
train anywhere in the frame, where the old detector fired on all thirty
sampled frames.
"""
import glob
from pathlib import Path

import cv2

HERE = Path(__file__).parent
ROOF = (0, 160, 348, 474)      # measured in the 854px views
TRAINED = HERE / 'runs' / 'wsr' / 'weights' / 'best.pt'


def on_roof(box, share=0.6):
    x1, y1 = max(box[0], ROOF[0]), max(box[1], ROOF[1])
    x2, y2 = min(box[2], ROOF[2]), min(box[3], ROOF[3])
    overlap = max(0, x2 - x1) * max(0, y2 - y1)
    area = (box[2] - box[0]) * (box[3] - box[1])
    return bool(area) and overlap / area > share


def count(model, clips, coco):
    from ultralytics import YOLO
    net = YOLO(str(model))
    total = roof = 0
    per_clip = {}
    for clip in clips:
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
        here_total = here_roof = 0
        for frame in frames[::10]:
            kwargs = {'classes': [6]} if coco else {}
            result = net.predict(frame, conf=0.45, verbose=False, **kwargs)[0]
            for box in result.boxes.xyxy.cpu().numpy():
                here_total += 1
                here_roof += on_roof([int(v) for v in box])
        per_clip[Path(clip).name] = (here_total, here_roof)
        total += here_total
        roof += here_roof
    return total, roof, per_clip


def main() -> None:
    clips = sorted(glob.glob(str(HERE / 'captures' / '*williton_2_dense.mp4')))
    clips = [c for c in clips if cv2.VideoCapture(c).get(cv2.CAP_PROP_FRAME_COUNT) > 0]
    print(f'{len(clips)} Williton 2 clips\n')
    for label, weights, coco in (('COCO yolo11s', HERE / 'yolo11s.pt', True),
                                 ('fine-tuned', TRAINED, False)):
        if not Path(weights).exists():
            print(f'{label}: no weights'); continue
        total, roof, per_clip = count(weights, clips, coco)
        print(f'{label:<14} {total:>4} detections, {roof:>4} on the roof '
              f'({roof / max(1, total):.0%})')
        for name, (t, r) in sorted(per_clip.items()):
            print(f'{"":<16} {name[9:17]}  {t:>3} det, {r:>3} roof')
        print()


if __name__ == '__main__':
    main()
