"""What is annotated at each camera, and what is still wrong with it.

Annotation is done by hand across eleven cameras and several sittings, so
the interesting question is not "is there data" but "is the data usable".
Four ways a camera can be annotated and still not work:

  no road          nothing traced, so detections cannot be placed at all
  half a road      one rail traced but not its pair, so there is no gauge
                   and therefore no scale
  traced too far   rails followed to the vanishing point, where a few
                   pixels of tracing error swamps the real gauge
  masked track     block-out painted over the running line, so the motion
                   gate cannot see a train where it actually runs

    python3 audit_annotations.py [--camera blue_anchor]
"""

import argparse

import track_geometry as tg
from wsr_live_capture import CALIBRATED, CAMERAS

FRAME_W, FRAME_H = 854, 480
MASKED_TRACK_SHARE = 0.05  # tolerate a little overlap at the far end

# Rails always converge at the far end, and project_onto() already
# withholds scale there rather than reporting a wrong one. So a trace
# that runs slightly too far is not a defect — only one that gives up a
# large part of the view is worth going back to.
MIN_USABLE_SHARE = 0.80


def raw_tracks(camera: str) -> list[dict]:
    """Tracks as written by the annotator, including half-traced ones.

    tracks_of() drops anything without both rails, which is exactly what
    an audit needs to report on.
    """
    entry = tg.TRACKS.get(camera) or {}
    if 'tracks' in entry:
        return entry['tracks']
    if 'rails' in entry:
        return [{'name': 'running line', 'kind': 'running', 'rails': entry['rails']}]
    return []


def rail_lengths(track: dict) -> tuple[int, int]:
    rails = track.get('rails') or {}
    return len(rails.get('a') or []), len(rails.get('b') or [])


def usable_share(camera: str, name: str) -> float:
    """Share of the centreline where the gauge is wide enough to trust."""
    samples = tg.centreline(camera, name)
    if not samples:
        return 0.0
    good = sum(s['gauge_px'] >= tg.MIN_RELIABLE_GAUGE_PX for s in samples)
    return good / len(samples)


def masked_share(camera: str, mask) -> float:
    """Share of centreline points sitting under the block-out mask."""
    hits = total = 0
    for track in tg.tracks_of(camera):
        for sample in tg.centreline(camera, track['name']):
            x, y = sample['point']
            xi = min(FRAME_W - 1, max(0, int(round(x))))
            yi = min(FRAME_H - 1, max(0, int(round(y))))
            total += 1
            hits += mask[yi, xi] > 0
    return hits / total if total else 0.0


def audit(camera: str) -> dict:
    tracks = raw_tracks(camera)
    mask = tg.exclusion_mask(camera, FRAME_W, FRAME_H)
    problems, notes = [], []

    complete = []
    for track in tracks:
        a, b = rail_lengths(track)
        if a < 2 or b < 2:
            problems.append(f"'{track['name']}' has only one rail traced "
                            f'({a} and {b} points) — no gauge, so no scale')
            continue
        complete.append(track)
        if min(a, b) == 2:
            # Under perspective a straight track really is a straight line,
            # so two points is right — but it cannot follow a curve, and
            # only the eye can tell which case this is.
            notes.append(f"'{track['name']}' traced as a straight line; "
                         f'add points if the track curves here')
        share = usable_share(camera, track['name'])
        if share < MIN_USABLE_SHARE:
            problems.append(f"'{track['name']}' gives usable scale over only "
                            f'{share:.0%} of its length')
        elif share < 1.0:
            notes.append(f"'{track['name']}' loses scale over the far "
                         f'{1 - share:.0%}, which the tracker already allows for')

    if not tracks:
        problems.append('no roads traced')
    if not tg.regions_of(camera, 'platform'):
        notes.append('no platform outlined, so calling and passing look alike')
    overlap = masked_share(camera, mask)
    if overlap > MASKED_TRACK_SHARE:
        problems.append(f'block-out covers {overlap:.0%} of the running line')

    return {
        'roads': len(complete),
        'partial': len(tracks) - len(complete),
        'platforms': len(tg.regions_of(camera, 'platform')),
        'occluders': len(tg.regions_of(camera, 'occluder')),
        'masked': float((mask > 0).mean()),
        'calibrated': camera in CALIBRATED,
        'problems': problems,
        'notes': notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera')
    args = parser.parse_args()

    names = [args.camera] if args.camera else list(CAMERAS)
    results = {name: audit(name) for name in names}

    print(f"{'camera':<28} {'roads':>5} {'plat':>5} {'occl':>5} "
          f"{'masked':>7}  status")
    ready = 0
    for name, row in results.items():
        state = 'ready' if not row['problems'] else f"{len(row['problems'])} issue(s)"
        ready += not row['problems']
        print(f"{name:<28} {row['roads']:>5} {row['platforms']:>5} "
              f"{row['occluders']:>5} {row['masked']:>6.0%}  {state}")

    print(f'\n{ready} of {len(results)} cameras ready to use')

    if any(r['problems'] for r in results.values()):
        print('\nNeeds work:')
        for name, row in results.items():
            for problem in row['problems']:
                print(f'  {name}: {problem}')

    if any(r['notes'] for r in results.values()):
        print('\nWorth an eye, but nothing is broken:')
        for name, row in results.items():
            for note in row['notes']:
                print(f'  {name}: {note}')

    unvalidated = [n for n, r in results.items()
                   if not r['calibrated'] and not r['problems']]
    if unvalidated:
        print(f'\nWatched, but with no validated northbound vector, so '
              f'direction comes from station order rather than drift:\n  '
              + ', '.join(unvalidated))


if __name__ == '__main__':
    main()
