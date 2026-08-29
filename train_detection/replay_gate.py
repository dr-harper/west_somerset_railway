"""Replay recorded clips through the motion gate, old mask against new.

The 29/8 gate log recorded only how much of the zone changed, never
where, so the false gates of that day cannot be re-judged. The clips can:
each one is a real train that the gate did open for. Running them back
answers the question the block-out raises — whether painting out the
crowds and the crossing traffic also painted out the trains.

Two masks per camera:

  old   the detect and approach zones as they stood on 29/8
  new   the same zones, or the traced corridor where a camera has none,
        with the painted block-out subtracted

A clip counts as caught when MOTION_CONSECUTIVE consecutive samples each
exceed MOTION_FRACTION of the mask, which is the watcher's own rule. The
clips run at 2fps, so three consecutive frames span the same 1.5s as
three live samples at MOTION_SAMPLE_S and the timing is faithful.

Absolute numbers here understate reality: every clip is an episode, so
every one did open the gate live, but the recording starts once the
episode is under way and may not contain the approach that triggered it.
The old-against-new difference is the meaningful figure, since both are
measured over the same frames.

Note that the new mask is a subset of the old, and the fraction is a mean
over mask pixels — so removing dead area can raise the fraction and catch
something the old mask missed. Losses and gains both occur.

    python3 replay_gate.py [--camera blue_anchor] [--limit 20]
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

import track_geometry as tg
from detection_zones import ZONES
from gala_watcher import (BACKGROUND_ALPHA, GLOBAL_JUMP_FRACTION,
                          MOTION_CONSECUTIVE, MOTION_FRACTION,
                          MOTION_THRESHOLD, PROC_H, PROC_W)

HERE = Path(__file__).parent


def zone_mask(camera: str) -> np.ndarray:
    mask = np.zeros((PROC_H, PROC_W), np.uint8)
    for _name, kind, poly in ZONES.get(camera, []):
        if kind in ('detect', 'approach'):
            pts = (np.array(poly, np.float32) * (PROC_W / 854)).astype(np.int32)
            cv2.fillPoly(mask, [pts], 255)
    return mask


def masks_for(camera: str) -> tuple[np.ndarray, np.ndarray]:
    """The gate mask as it was on 29/8, and as it stands now."""
    old = zone_mask(camera)
    new = old.copy() if old.any() else tg.corridor_mask(camera, PROC_W, PROC_H)
    new[tg.exclusion_mask(camera, PROC_W, PROC_H) > 0] = 0
    return old, new


def gate_opens(frames: list, mask: np.ndarray) -> tuple[bool, float]:
    """Whether the watcher's gate rule fires, and the peak zone fraction."""
    if not mask.any():
        return False, 0.0
    background = None
    consecutive = 0
    peak = 0.0
    for frame in frames:
        small = cv2.resize(frame, (PROC_W, PROC_H))
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        grey = cv2.GaussianBlur(grey, (5, 5), 0)
        if background is None:
            background = grey.copy()
            continue
        diff = cv2.absdiff(grey, background)
        changed = (diff > MOTION_THRESHOLD).astype(np.uint8)
        if float(changed.mean()) > GLOBAL_JUMP_FRACTION:
            background = None          # exposure jump, as the watcher does
            consecutive = 0
            continue
        fraction = float(changed[mask > 0].mean())
        peak = max(peak, fraction)
        consecutive = consecutive + 1 if fraction > MOTION_FRACTION else 0
        if consecutive >= MOTION_CONSECUTIVE:
            return True, peak
        cv2.accumulateWeighted(grey, background, BACKGROUND_ALPHA)
    return False, peak


def read_clip(path: Path, stride: int = 1) -> list:
    cap = cv2.VideoCapture(str(path))
    frames = []
    index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if index % stride == 0:
            frames.append(frame)
        index += 1
    cap.release()
    return frames


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()

    episodes = [json.loads(line) for line in
                (HERE / 'episodes.jsonl').read_text().splitlines() if line.strip()]
    episodes = [e for e in episodes if e.get('clip')]
    if args.camera:
        episodes = [e for e in episodes if e['camera'] == args.camera]
    if args.limit:
        episodes = episodes[:args.limit]

    cache: dict = {}
    rows = []
    for episode in episodes:
        clip = HERE / 'captures' / episode['clip']
        if not clip.exists():
            clip = HERE / episode['clip']
        if not clip.exists():
            continue
        frames = read_clip(clip)
        if len(frames) < MOTION_CONSECUTIVE + 1:
            continue
        camera = episode['camera']
        if camera not in cache:
            cache[camera] = masks_for(camera)
        old_mask, new_mask = cache[camera]
        old_open, old_peak = gate_opens(frames, old_mask)
        new_open, new_peak = gate_opens(frames, new_mask)
        rows.append({'camera': camera, 't': episode['t_enter'],
                     'old': old_open, 'new': new_open,
                     'old_peak': old_peak, 'new_peak': new_peak,
                     'frames': len(frames)})

    if not rows:
        print('No clips found to replay.')
        return

    print(f"{'camera':<26} {'clips':>6} {'caught before':>14} {'caught now':>11} "
          f"{'lost':>5}")
    for camera in sorted({r['camera'] for r in rows}):
        mine = [r for r in rows if r['camera'] == camera]
        before = sum(r['old'] for r in mine)
        now = sum(r['new'] for r in mine)
        lost = sum(r['old'] and not r['new'] for r in mine)
        print(f'{camera:<26} {len(mine):>6} {before:>14} {now:>11} {lost:>5}')

    lost = [r for r in rows if r['old'] and not r['new']]
    gained = [r for r in rows if r['new'] and not r['old']]
    print(f"\n{sum(r['old'] for r in rows)} of {len(rows)} clips opened the old "
          f"gate, {sum(r['new'] for r in rows)} open the new one")
    if lost:
        print(f'\n{len(lost)} train(s) the block-out would now hide:')
        for r in lost:
            print(f"  {r['camera']} {r['t'][11:]}  peak fell "
                  f"{r['old_peak']:.3f} -> {r['new_peak']:.3f}")
    if gained:
        print(f'\n{len(gained)} newly caught, the smaller mask concentrating '
              f'the moving fraction:')
        for r in gained:
            print(f"  {r['camera']} {r['t'][11:]}  peak rose "
                  f"{r['old_peak']:.3f} -> {r['new_peak']:.3f}")


if __name__ == '__main__':
    main()
