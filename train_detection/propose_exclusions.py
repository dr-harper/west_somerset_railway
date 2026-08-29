"""Propose motion-mask exclusions from a run's own false gates.

Automatic masking by monocular depth is tempting but solves the wrong
problem: a person on a platform stands at essentially the same depth as a
train on the adjacent track, so depth cannot separate them. Semantic
segmentation could, but "railway track" is not a standard class and
open-vocabulary models are not reliable enough to trust unsupervised.

The watcher already generates better evidence than either. Every gate
records which cells of a coarse grid moved, and whether the gate then
found a train. Cells that move often and never yield a train are, by
definition, what the gate should stop looking at — crowds, road traffic,
vegetation. This turns a day's false gates into a proposed mask, drawn
over the camera's reference frame for a human to accept or reject.

    python3 propose_exclusions.py [--camera blue_anchor] [--min-ratio 0.9]
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2

from gala_watcher import MOTION_GRID_H, MOTION_GRID_W

HERE = Path(__file__).parent
GATE_LOG = HERE / 'gate_log.jsonl'
FRAME_W, FRAME_H = 854, 480


def load_gates() -> tuple[dict, dict]:
    """Per camera, how often each grid cell moved on gates, and on false ones."""
    all_gates: dict[str, defaultdict] = defaultdict(lambda: defaultdict(int))
    false_gates: dict[str, defaultdict] = defaultdict(lambda: defaultdict(int))
    if not GATE_LOG.exists():
        return all_gates, false_gates
    for line in GATE_LOG.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cells = row.get('cells')
        if not cells:
            continue
        if row['kind'] == 'gate':
            for cell in cells:
                all_gates[row['camera']][cell] += 1
        elif row['kind'] == 'false_gate':
            for cell in cells:
                false_gates[row['camera']][cell] += 1
    return all_gates, false_gates


def cell_box(cell: int) -> tuple[int, int, int, int]:
    row, col = divmod(cell, MOTION_GRID_W)
    w, h = FRAME_W // MOTION_GRID_W, FRAME_H // MOTION_GRID_H
    return col * w, row * h, w, h


def propose(camera: str, all_gates, false_gates, min_ratio: float,
            min_events: int) -> list[int]:
    """Cells that fire often and almost never produce a train."""
    proposed = []
    for cell, total in all_gates.get(camera, {}).items():
        if total < min_events:
            continue                      # too rare to judge
        wasted = false_gates.get(camera, {}).get(cell, 0)
        if wasted / total >= min_ratio:
            proposed.append(cell)
    return sorted(proposed)


def render(camera: str, cells: list[int], all_gates, false_gates) -> str | None:
    frame_path = HERE / 'working_images' / f'cam_{camera}.jpg'
    if not frame_path.exists():
        return None
    frame = cv2.resize(cv2.imread(str(frame_path)), (FRAME_W, FRAME_H))
    overlay = frame.copy()
    for cell, total in all_gates.get(camera, {}).items():
        x, y, w, h = cell_box(cell)
        wasted = false_gates.get(camera, {}).get(cell, 0)
        ratio = wasted / total if total else 0
        # red where motion is wasted, green where it earns its keep
        colour = (60, 60, 220) if cell in cells else (
            int(80 + 120 * ratio), int(180 - 100 * ratio), 60)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), colour, -1)
        cv2.putText(overlay, str(total), (x + 3, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
    out = cv2.addWeighted(overlay, 0.45, frame, 0.55, 0)
    for cell in cells:
        x, y, w, h = cell_box(cell)
        cv2.rectangle(out, (x, y), (x + w, y + h), (60, 60, 220), 2)
    cv2.putText(out, f'{camera}: {len(cells)} cells proposed for exclusion',
                (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    path = HERE / 'working_images' / f'proposed_exclusions_{camera}.jpg'
    cv2.imwrite(str(path), out)
    return str(path)


def as_regions(cells: list[int]) -> list[dict]:
    """Proposed cells as annotator-compatible rectangular regions."""
    regions = []
    for cell in cells:
        x, y, w, h = cell_box(cell)
        regions.append({
            'name': f'auto-exclude cell {cell}',
            'kind': 'exclude',
            'points': [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
            'auto': True,
        })
    return regions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera')
    parser.add_argument('--min-ratio', type=float, default=0.95,
                        help='share of a cell\'s gates that must be false')
    parser.add_argument('--min-events', type=int, default=5,
                        help='ignore cells seen fewer times than this')
    parser.add_argument('--write', action='store_true',
                        help='append proposals to camera_tracks.json')
    args = parser.parse_args()

    all_gates, false_gates = load_gates()
    if not all_gates:
        print('No gate data with cell positions yet. Cell logging was added '
              'after the 29/8 run, so this needs a fresh watcher run.')
        return

    cameras = [args.camera] if args.camera else sorted(all_gates)
    for camera in cameras:
        cells = propose(camera, all_gates, false_gates,
                        args.min_ratio, args.min_events)
        total_cells = len(all_gates.get(camera, {}))
        print(f'{camera}: {len(cells)} of {total_cells} active cells proposed '
              f'for exclusion')
        image = render(camera, cells, all_gates, false_gates)
        if image:
            print(f'   rendered {image}')
        if args.write and cells:
            path = HERE / 'camera_tracks.json'
            data = json.loads(path.read_text()) if path.exists() else {}
            entry = data.setdefault(camera, {})
            regions = [r for r in entry.get('regions', []) if not r.get('auto')]
            entry['regions'] = regions + as_regions(cells)
            path.write_text(json.dumps(data, indent=1))
            print(f'   wrote {len(cells)} auto regions (existing hand-drawn '
                  f'ones kept)')


if __name__ == '__main__':
    main()
