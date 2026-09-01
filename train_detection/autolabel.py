"""Label without a human, by exploiting what furniture cannot do.

A train is somewhere different every time. A roof is not. Over a day of
detections the false positives collapse into a tight knot at one set of
coordinates — the same box, to within a few pixels, hundreds of times —
while real trains scatter across the frame. That difference needs no
labels to find, and it is the single strongest signal available.

The residual risk is a platform where trains genuinely do stop in the
same place, so a cluster is only called furniture when it is both tight
and unusually persistent.
"""
import glob
from collections import defaultdict
import cv2, numpy as np
from gala_watcher import SharedDetector

det = SharedDetector('yolo11s.pt')
found = defaultdict(list)
for path in sorted(glob.glob('captures/*_key.jpg')):
    frame = cv2.imread(path)
    if frame is None:
        continue
    h, w = frame.shape[:2]
    camera = '_'.join(path.split('/')[-1].replace('_key.jpg', '').split('_')[1:])
    for conf, box, _c in det.trains(frame, conf=0.4):
        x1, y1, x2, y2 = box
        found[camera].append((np.array([(x1+x2)/2/w, (y1+y2)/2/h,
                                        (x2-x1)/w, (y2-y1)/h]), conf, path))

def cluster(points, tol=0.04):
    """Greedy grouping: boxes agreeing on all four numbers to within tol."""
    groups = []
    for vec, conf, path in points:
        for g in groups:
            if np.abs(g['centre'] - vec).max() < tol:
                g['members'].append((vec, conf, path))
                g['centre'] = np.mean([m[0] for m in g['members']], axis=0)
                break
        else:
            groups.append({'centre': vec, 'members': [(vec, conf, path)]})
    return sorted(groups, key=lambda g: -len(g['members']))

print(f"{'camera':<28} {'dets':>5} {'largest cluster':>16} {'share':>7}  verdict")
for camera in sorted(found):
    groups = cluster(found[camera])
    top = groups[0]
    share = len(top['members']) / len(found[camera])
    cx, cy, bw, bh = top['centre']
    verdict = ('FURNITURE — same box every time'
               if len(top['members']) >= 8 and share >= 0.30 else 'no fixed cluster')
    print(f'{camera:<28} {len(found[camera]):>5} {len(top["members"]):>16} '
          f'{share:>6.0%}  {verdict}')
    if verdict.startswith('FURNITURE'):
        print(f'{"":<28}   at cx={cx:.2f} cy={cy:.2f} w={bw:.2f} h={bh:.2f}, '
              f'conf up to {max(m[1] for m in top["members"]):.2f}')
