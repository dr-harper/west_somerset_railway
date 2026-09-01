"""Fine-tune YOLO to see what a train is made of: wagons and locomotives.

COCO taught the detector what a train looks like in a photograph taken by
a person. It has never seen a station roof from a pole at thirty degrees,
so it calls the Williton roof a train at 0.92 and there is no threshold
that separates the two — to this model they genuinely look alike.

The fix is to show it. Two hundred and fifty reviewed frames is small for
training from scratch and ample for adapting a model that already knows
what rolling stock is, because the domain is closed: eleven fixed
cameras, and it only ever has to recognise these eleven scenes.

The negatives matter as much as the boxes. Thirty frames here contain no
train at all — roof, café hut, crossing gate, tarpaulined plant — and an
empty label file is how the detector is told those are background.

Judged on false positives per camera rather than mAP: the number that
broke was Williton 2 logging 91 episodes to Williton 1's 20.

    python3 train_detector.py --epochs 60
    python3 train_detector.py --compare        # old vs new, on the val set
"""

import argparse
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / 'dataset_formation' / 'data.yaml'
RUNS = HERE / 'runs'
BASE = 'yolo11s.pt'


def train(epochs: int, imgsz: int, batch: int, device: str, patience: int) -> None:
    from ultralytics import YOLO

    model = YOLO(str(HERE / BASE))
    model.train(
        data=str(DATA), epochs=epochs, imgsz=imgsz, batch=batch,
        device=device, patience=patience,
        project=str(RUNS), name='formation', exist_ok=True,
        # The cameras never move and the trains are always the right way
        # up, so the usual augmentations mostly invent situations that
        # cannot occur. Flipping horizontally would teach it that Bishops
        # Lydeard's platform is on the other side, which it never is.
        fliplr=0.0, flipud=0.0, degrees=0.0, perspective=0.0,
        mosaic=0.0,          # stitching four views together destroys the
                             # fixed geometry that makes this domain easy
        scale=0.2, translate=0.05,
        hsv_h=0.015, hsv_s=0.5, hsv_v=0.4,   # weather and time of day do vary
        workers=2,           # the watcher is capturing; leave it room
        val=True, plots=True, seed=0,
    )
    print(f'\nweights: {RUNS / "wsr" / "weights" / "best.pt"}')


def compare(device: str) -> None:
    """Old model and new one, on the same held-out frames."""
    from ultralytics import YOLO

    trained = RUNS / 'formation' / 'weights' / 'best.pt'
    if not trained.exists():
        print('nothing trained yet')
        return
    for label, weights in (('COCO yolo11s', HERE / BASE), ('fine-tuned', trained)):
        model = YOLO(str(weights))
        # classes=[6] for the COCO model, whose 'train' is class 6; the
        # fine-tuned one has a single class, so no filter applies.
        kwargs = {'classes': [6]} if 'yolo11s.pt' in str(weights) else {}
        result = model.val(data=str(DATA), device=device, verbose=False,
                           plots=False, **kwargs)
        box = result.box
        print(f'{label:<14} mAP50 {box.map50:.3f}  precision {box.mp:.3f}  '
              f'recall {box.mr:.3f}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=60)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--batch', type=int, default=8)
    parser.add_argument('--device', default='mps')
    parser.add_argument('--patience', type=int, default=15)
    parser.add_argument('--compare', action='store_true')
    args = parser.parse_args()
    if args.compare:
        compare(args.device)
    else:
        train(args.epochs, args.imgsz, args.batch, args.device, args.patience)


if __name__ == '__main__':
    main()
