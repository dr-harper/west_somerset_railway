"""Propose one box per vehicle, using SAM rather than a threshold.

Counting vehicles by hand-built signal failed three times in a row — the
lightness notches counted windows, the full-height darkness rule was
physically impossible because gangwayed stock has no gap, and the livery
test caught an edge artefact. What does work is asking a segmenter: given
a point on a coach roof, SAM returns that coach and stops at its end.

So the rake is found first with the fine-tuned detector, points are
sampled along the top of its mask, and each point is put to SAM. The
masks that come back overlap heavily where two points landed on the same
vehicle, so they are merged; what survives is one region per vehicle.

These are proposals for review, not labels. The point is to make the
labelling cheap enough to be worth doing, not to skip it.

    python3 propose_vehicles.py <image> [more images...]
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
SAMPLES = 9          # points along the roofline
MERGE_IOU = 0.35     # masks agreeing this much are the same vehicle


def rake_mask(image, seg):
    """The whole train, as pixels."""
    result = seg.predict(image, conf=0.4, classes=[6], verbose=False)[0]
    if result.masks is None:
        return None
    height, width = image.shape[:2]
    masks = [cv2.resize(m.astype(np.float32), (width, height)) > 0.5
             for m in result.masks.data.cpu().numpy()]
    return max(masks, key=lambda m: m.sum()) if masks else None


def roof_points(mask, count=SAMPLES):
    """Points just inside the top edge of the rake, spread along it.

    Just inside rather than on it: a point exactly on the boundary lands
    as often on the sky behind as on the roof, and SAM answers whichever
    it hit.
    """
    columns = np.where(mask.any(axis=0))[0]
    if len(columns) < 40:
        return []
    x0, x1 = columns.min(), columns.max()
    points = []
    for x in np.linspace(x0 + 8, x1 - 8, count).astype(int):
        rows = np.where(mask[:, x])[0]
        if len(rows) < 12:
            continue
        # a tenth of the way down the body, measured at this column
        points.append([int(x), int(rows.min() + (rows.max() - rows.min()) * 0.12)])
    return points


def overlap(a, b) -> float:
    both = (a & b).sum()
    return both / max(1, (a | b).sum())


def vehicles(image, seg, sam):
    mask = rake_mask(image, seg)
    if mask is None:
        return [], None
    points = roof_points(mask)
    if not points:
        return [], mask
    height, width = image.shape[:2]

    found = []
    for point in points:
        result = sam.predict(image, points=[point], labels=[1], verbose=False)[0]
        if result.masks is None:
            continue
        for raw in result.masks.data.cpu().numpy():
            piece = cv2.resize(raw.astype(np.float32), (width, height)) > 0.5
            # Only what is actually part of the train: SAM will happily
            # return the station roof if a point strayed onto it.
            if (piece & mask).sum() / max(1, piece.sum()) < 0.6:
                continue
            if piece.sum() < 800:
                continue
            found.append(piece)

    merged = []
    for piece in sorted(found, key=lambda m: -m.sum()):
        if all(overlap(piece, kept) < MERGE_IOU for kept in merged):
            merged.append(piece)
    # Not filtered by share of the rake. The nearest coach genuinely is
    # most of it — at Williton it measured 83% of the rake's pixels, being
    # closest to the camera — and discarding it left the biggest vehicle
    # in the frame uncounted. What marks the rake itself is reaching from
    # one end of it to the other, which no single vehicle does.
    columns = np.where(mask.any(axis=0))[0]
    span = columns.max() - columns.min()
    keep = []
    for piece in merged:
        cols = np.where(piece.any(axis=0))[0]
        if len(cols) and (cols.max() - cols.min()) < 0.92 * span:
            keep.append(piece)
    return keep, mask


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('images', nargs='+')
    parser.add_argument('--out', default='working_images/vehicles_proposed.jpg')
    args = parser.parse_args()

    from ultralytics import SAM, YOLO
    seg = YOLO(str(HERE / 'yolo11s-seg.pt'))
    sam = SAM(str(HERE / 'mobile_sam.pt'))

    colours = [(60, 220, 255), (90, 240, 90), (255, 130, 60),
               (220, 90, 220), (255, 255, 110), (120, 160, 255)]
    tiles = []
    for path in args.images:
        image = cv2.imread(path)
        if image is None:
            continue
        parts, mask = vehicles(image, seg, sam)
        print(f'{Path(path).name[9:]:<36} {len(parts)} vehicles proposed')
        vis = image.copy()
        for i, piece in enumerate(parts):
            colour = colours[i % len(colours)]
            vis[piece] = (0.45 * np.array(colour) + 0.55 * vis[piece]).astype(np.uint8)
            ys, xs = np.where(piece)
            cv2.rectangle(vis, (xs.min(), ys.min()), (xs.max(), ys.max()), colour, 2)
        tile = cv2.resize(vis, (640, 360))
        bar = np.zeros((22, 640, 3), np.uint8)
        cv2.putText(bar, f'{Path(path).name[9:]}  {len(parts)} vehicles', (6, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, tile]))
    if tiles:
        while len(tiles) % 2:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]
        cv2.imwrite(args.out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f'-> {args.out}')


if __name__ == '__main__':
    main()
