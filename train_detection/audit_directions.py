"""Check direction labels against evidence that does not come from drift.

Auditing direction against the movements the tracker built proves
nothing: chaining rejects any sighting whose label disagrees with the
heading it is building, so agreement is guaranteed by construction. Run
that way the system scores 33 out of 33 while being wrong.

The independent evidence is the locomotive itself. Where the classifier
has read a running number off a still, the timetable says which way that
engine was working at that hour — a fact established without reference to
how anything moved in the image. Comparing the label against that is a
real test.

What it found at Bishops Lydeard: drift of (-311,+140) was a northbound
working and (-349,+243) a southbound one. Two nearly parallel drifts,
opposite truths, so no single vector can separate them and the camera
belongs with Watchet in UNRELIABLE_DRIFT_CAMERAS.

    python3 audit_directions.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
APP_DATA = HERE / '../app/wsr-railway-app/src/data'

MATCH_WINDOW_MIN = 40


def _minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


def booked_direction(timetable: dict, day: str, station: str,
                     number: str, observed: str) -> tuple[str, str] | None:
    """Which way the timetable had that locomotive working, and when.

    Only where the engine has a single plausible call at that station near
    the time: a loco that could be explained by two different workings is
    no evidence at all.
    """
    entry = timetable['days'].get(day)
    if not entry or entry.get('kind') != 'service':
        return None
    services = timetable['patterns'][entry['pattern']]['services']
    seen = _minutes(observed[11:16])
    candidates = []
    for service in services:
        if (service.get('loco') or '').upper() != number.upper():
            continue
        for stop in service['stops']:
            if stop['c'] != station:
                continue
            when = stop.get('d') or stop.get('a')
            if not when:
                continue
            if abs(_minutes(when) - seen) <= MATCH_WINDOW_MIN:
                candidates.append((service['direction'], when))
    if len(candidates) != 1:
        return None
    heading, when = candidates[0]
    return ('northbound' if heading == 'NB' else 'southbound', when)


def main() -> None:
    from train_tracker import CAMERA_NODES

    episodes = [json.loads(line) for line
                in (HERE / 'episodes.jsonl').read_text().splitlines() if line.strip()]
    classifications = json.loads((HERE / 'classifications.json').read_text())
    timetable = json.loads((APP_DATA / 'timetable2026.json').read_text())

    per_camera: dict[str, list] = {}
    for episode in episodes:
        station = CAMERA_NODES.get(episode['camera'])
        number = (classifications.get(episode['t_enter']) or {}).get('number')
        if not station or not number:
            continue
        truth = booked_direction(timetable, episode['t_enter'][:10], station,
                                 number, episode['t_enter'])
        if not truth:
            continue
        per_camera.setdefault(episode['camera'], []).append({
            'at': episode['t_enter'][11:19],
            'number': number,
            'drift': episode.get('drift_px'),
            'label': episode.get('direction'),
            'truth': truth[0],
            'booked': truth[1],
        })

    if not per_camera:
        print('No episodes carry both a read running number and a booked '
              'working to check against.')
        return

    print(f"{'camera':<28} {'right':>6} {'wrong':>6} {'unclear':>8}")
    for camera, rows in sorted(per_camera.items()):
        right = sum(1 for r in rows if r['label'] == r['truth'])
        wrong = sum(1 for r in rows
                    if r['label'] in ('northbound', 'southbound')
                    and r['label'] != r['truth'])
        unclear = sum(1 for r in rows
                      if r['label'] not in ('northbound', 'southbound'))
        flag = '  <-- drift is not telling the truth here' if wrong else ''
        print(f'{camera:<28} {right:>6} {wrong:>6} {unclear:>8}{flag}')

    print('\nEvery checked sighting:')
    for camera, rows in sorted(per_camera.items()):
        for r in rows:
            drift = r['drift'] or [0, 0]
            mark = ('ok   ' if r['label'] == r['truth']
                    else '     ' if r['label'] not in ('northbound', 'southbound')
                    else 'WRONG')
            print(f"  {mark} {camera:<26} {r['at']} {r['number']:<7} "
                  f"drift ({drift[0]:+5},{drift[1]:+5})  "
                  f"said {str(r['label']):<11} was {r['truth']} "
                  f"(booked {r['booked']})")


if __name__ == '__main__':
    main()
