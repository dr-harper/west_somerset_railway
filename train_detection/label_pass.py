"""Review proposed boxes in sheets, and record the verdicts.

Twelve frames to a sheet, every proposal numbered. A person — or a model
looking at the sheet — calls each number accept or reject, and the
verdicts land in labels.json. Rejecting every proposal in a frame is not
a wasted frame: it becomes a negative, which is how the detector is told
that the Williton roof is a roof.

    python3 label_pass.py --sheets        # build the sheets to review
    python3 label_pass.py --apply FILE    # fold verdicts into labels.json
    python3 label_pass.py --export        # write YOLO .txt label files
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
DATA = HERE / 'dataset'
SHEETS = HERE / 'working_images' / 'sheets'
LABELS = DATA / 'labels.json'
PER_CAMERA = 25
PER_SHEET = 12
EMPTY_SHARE = 0.2       # frames the model saw nothing in, kept as negatives


def select(seed: int = 11) -> list:
    """A spread per camera: mostly proposals, some empties, many sources."""
    proposals = json.loads((DATA / 'proposals.json').read_text())
    by_camera = defaultdict(list)
    for key, entry in proposals.items():
        by_camera[entry['camera']].append((key, entry))

    rng = random.Random(seed)
    chosen = []
    for camera in sorted(by_camera):
        items = by_camera[camera]
        withbox = [i for i in items if i[1]['proposals']]
        empty = [i for i in items if not i[1]['proposals']]
        want_empty = min(len(empty), int(PER_CAMERA * EMPTY_SHARE))
        want_box = min(len(withbox), PER_CAMERA - want_empty)
        # Spread across sources so a single clip cannot fill a camera's quota.
        def spread(pool, want):
            groups = defaultdict(list)
            for item in pool:
                groups[item[1]['source']].append(item)
            picked, sources = [], sorted(groups)
            while len(picked) < want and any(groups[s] for s in sources):
                for source in sources:
                    if groups[source] and len(picked) < want:
                        picked.append(groups[source].pop(
                            rng.randrange(len(groups[source]))))
            return picked
        chosen += spread(withbox, want_box) + spread(empty, want_empty)
    return chosen


def build_sheets() -> None:
    chosen = select()
    SHEETS.mkdir(parents=True, exist_ok=True)
    for old in SHEETS.glob('*.jpg'):
        old.unlink()

    index = {}
    frame_numbers = {}
    number = 0
    tiles = []
    for key, entry in chosen:
        image = cv2.imread(str(DATA / 'images' / entry['split'] / f'{key}.jpg'))
        if image is None:
            continue
        height, width = image.shape[:2]
        marks = []
        for proposal in entry['proposals']:
            number += 1
            x1 = int((proposal['cx'] - proposal['w'] / 2) * width)
            y1 = int((proposal['cy'] - proposal['h'] / 2) * height)
            x2 = int((proposal['cx'] + proposal['w'] / 2) * width)
            y2 = int((proposal['cy'] + proposal['h'] / 2) * height)
            cv2.rectangle(image, (x1, y1), (x2, y2), (60, 200, 255),
                          max(2, width // 400))
            tag = f'{number}'
            scale, thick = width / 900, max(2, width // 320)
            cv2.putText(image, tag, (x1 + 5, max(24, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3,
                        cv2.LINE_AA)
            cv2.putText(image, tag, (x1 + 5, max(24, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, scale, (60, 200, 255), thick,
                        cv2.LINE_AA)
            index[number] = {'frame': key, 'camera': entry['camera'],
                             'split': entry['split'],
                             'box': [proposal['cx'], proposal['cy'],
                                     proposal['w'], proposal['h']],
                             'conf': proposal['conf']}
            marks.append(number)

        frame_no = len(tiles) + 1
        frame_numbers[frame_no] = key
        tile = cv2.resize(image, (480, 270))
        bar = np.zeros((22, 480, 3), np.uint8)
        label = (f"F{frame_no} {entry['camera']}  " +
                 (f"boxes {marks[0]}-{marks[-1]}" if len(marks) > 1
                  else f"box {marks[0]}" if marks else 'EMPTY - check'))
        cv2.putText(bar, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append((np.vstack([bar, tile]), key))

    frames = {}
    for sheet_no, start in enumerate(range(0, len(tiles), PER_SHEET), 1):
        batch = tiles[start:start + PER_SHEET]
        cells = [t for t, _ in batch]
        while len(cells) % 4:
            cells.append(np.zeros_like(cells[0]))
        rows = [np.hstack(cells[i:i + 4]) for i in range(0, len(cells), 4)]
        path = SHEETS / f'sheet_{sheet_no:02d}.jpg'
        cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])
        for _, key in batch:
            frames[key] = sheet_no

    (DATA / 'review_index.json').write_text(json.dumps(
        {'proposals': index, 'frames': frames,
         'frame_numbers': frame_numbers,
         'selected': [k for k, _ in chosen]}, indent=1))
    print(f'{len(chosen)} frames selected, {number} proposals numbered')
    print(f'{len(list(SHEETS.glob("*.jpg")))} sheets in {SHEETS}')
    per = defaultdict(int)
    for _, entry in chosen:
        per[entry['camera']] += 1
    for camera in sorted(per):
        print(f'  {camera:<28} {per[camera]:>3}')


def apply_verdicts(path: str) -> None:
    """Fold a {number: 'accept'|'reject'} file into the running labels."""
    verdicts = json.loads(Path(path).read_text())
    index = json.loads((DATA / 'review_index.json').read_text())
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    excluded = set(verdicts.pop('exclude_frames', []))
    index_frames = json.loads((DATA / 'review_index.json').read_text())
    for frame_no in excluded:
        key = index_frames['frame_numbers'].get(str(frame_no))
        if key:
            labels.pop(key, None)
    for number, verdict in verdicts.items():
        entry = index['proposals'].get(str(number))
        if not entry:
            print(f'  no such proposal: {number}')
            continue
        frame = labels.setdefault(entry['frame'], {
            'camera': entry['camera'], 'split': entry['split'], 'boxes': []})
        if verdict == 'accept':
            frame['boxes'].append(entry['box'])
    # A selected frame with no accepted box is a negative, and must be
    # recorded as reviewed rather than left looking unlabelled.
    skip = {index['frame_numbers'].get(str(n)) for n in excluded}
    for key in index['selected']:
        if key in skip:
            continue
        info = index['frames']
        labels.setdefault(key, {
            'camera': next((v['camera'] for v in index['proposals'].values()
                            if v['frame'] == key), '?'),
            'split': next((v['split'] for v in index['proposals'].values()
                           if v['frame'] == key), 'train'),
            'boxes': []})
    LABELS.write_text(json.dumps(labels, indent=1))
    kept = sum(len(v['boxes']) for v in labels.values())
    negatives = sum(1 for v in labels.values() if not v['boxes'])
    print(f'{len(labels)} frames labelled, {kept} boxes kept, '
          f'{negatives} negatives')



def clamp(box: list) -> tuple:
    """Keep a box inside the picture.

    A box drawn by hand near an edge can run a pixel or two past it, and
    a train entering the frame legitimately has its box clipped by it.
    YOLO rejects a label outside [0, 1], so the edges are trimmed and the
    centre and size recomputed from them rather than the box discarded —
    a train at the frame edge is exactly the case worth keeping.
    """
    cx, cy, w, h = box
    x1, y1 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x2, y2 = min(1.0, cx + w / 2), min(1.0, cy + h / 2)
    return ((x1 + x2) / 2, (y1 + y2) / 2, max(0.0, x2 - x1), max(0.0, y2 - y1))


def export() -> None:
    """Write YOLO labels, and the file lists that keep the set honest.

    dataset/images holds every candidate frame, but only the reviewed ones
    have labels. Pointing training at the directory would hand YOLO 848
    unlabelled images and it treats an image with no label file as pure
    background — so every train in them would become an example of 'not a
    train', which is the exact mistake this whole exercise exists to undo.

    So training reads a list of the reviewed frames instead of a folder.
    An empty .txt is written for a negative on purpose: that is how YOLO
    is told 'this frame really does contain nothing', as opposed to 'this
    frame was never looked at'.
    """
    labels = json.loads(LABELS.read_text())
    listed = defaultdict(list)
    for key, entry in labels.items():
        split = entry['split']
        image = DATA / 'images' / split / f'{key}.jpg'
        if not image.exists():
            print(f'  no image for {key}, skipped')
            continue
        out = DATA / 'labels' / split
        out.mkdir(parents=True, exist_ok=True)
        (out / f'{key}.txt').write_text('\n'.join(
            '0 ' + ' '.join(f'{v:.6f}' for v in clamp(b))
            for b in entry['boxes']))
        listed[split].append(str(image.resolve()))

    for split, paths in listed.items():
        (DATA / f'{split}.txt').write_text('\n'.join(sorted(paths)))
        empties = sum(1 for p in paths
                      if not (DATA / 'labels' / split /
                              (Path(p).stem + '.txt')).read_text().strip())
        print(f'  {split}: {len(paths)} images listed, {empties} negatives')

    (DATA / 'data.yaml').write_text(
        f'path: {DATA.resolve()}\n'
        f'train: train.txt\n'
        f'val: val.txt\n'
        'names:\n  0: train\n')
    print(f'  wrote {DATA / "data.yaml"}')


def build_queue() -> None:
    """One file the review page can load, in the order worth reviewing.

    Ordered by how much a mistake costs rather than by camera: the frames
    called empty come first, because a train hidden in a negative teaches
    the detector to ignore it; then the boxes rejected, where the cost is
    only a missing label; then the accepts, which are mostly obvious.
    """
    index = json.loads((DATA / 'review_index.json').read_text())
    labels = json.loads(LABELS.read_text())
    verdicts = json.loads((HERE / 'verdicts.json').read_text())
    excluded = {index['frame_numbers'].get(str(n))
                for n in verdicts.get('exclude_frames', [])}

    rejected_by_frame = defaultdict(list)
    for number, verdict in verdicts.items():
        if number == 'exclude_frames' or verdict != 'reject':
            continue
        entry = index['proposals'][number]
        rejected_by_frame[entry['frame']].append(entry['box'])

    queue = []
    for key, entry in labels.items():
        if not entry['boxes']:
            flag, note = 'negative', 'Called empty — is there a train in it?'
        elif key in rejected_by_frame:
            flag, note = 'rejected', 'Something here was rejected — right call?'
        else:
            flag, note = 'accepted', ''
        queue.append({
            'key': key, 'camera': entry['camera'], 'split': entry['split'],
            'image': f"dataset/images/{entry['split']}/{key}.jpg",
            'boxes': entry['boxes'],
            'dropped': rejected_by_frame.get(key, []),
            'flag': flag, 'note': note,
        })
    for key in sorted(x for x in excluded if x):
        entry = next((v for v in index['proposals'].values()
                      if v['frame'] == key), None)
        split = entry['split'] if entry else 'train'
        queue.append({
            'key': key,
            'camera': entry['camera'] if entry else '?',
            'split': split,
            'image': f'dataset/images/{split}/{key}.jpg',
            'boxes': [], 'dropped': [], 'flag': 'excluded',
            'note': 'Left out — a train the model missed. Draw it to bring it back.',
        })

    order = {'negative': 0, 'rejected': 1, 'excluded': 2, 'accepted': 3}
    queue.sort(key=lambda q: (order[q['flag']], q['camera'], q['key']))
    (DATA / 'review_queue.json').write_text(json.dumps(queue, indent=1))
    counts = defaultdict(int)
    for item in queue:
        counts[item['flag']] += 1
    print(f'{len(queue)} frames queued: ' +
          ', '.join(f'{n} {f}' for f, n in sorted(counts.items())))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sheets', action='store_true')
    parser.add_argument('--apply')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--queue', action='store_true',
                        help='write the file label_review.html reads')
    args = parser.parse_args()
    if args.sheets:
        build_sheets()
    elif args.apply:
        apply_verdicts(args.apply)
    elif args.export:
        export()
    elif args.queue:
        build_queue()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
