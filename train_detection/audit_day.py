"""How a day's detection actually went, in the terms that matter.

Counting detections flatters the system. One train standing in the
Williton loop produced twenty-five episodes on 30/8 — each a real train,
correctly identified, and all the same train not going anywhere. The
numbers worth reading are how much of the day's booked service was seen,
how much work the gate wasted, and whether anything genuinely unbooked
happened.

    python3 audit_day.py [--date 2026-08-30]
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
APP_DATA = HERE / '../app/wsr-railway-app/src/data'


def load(name: str) -> list[dict]:
    path = HERE / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def duration_s(episode: dict) -> float | None:
    if not episode.get('t_exit'):
        return None
    return (datetime.fromisoformat(episode['t_exit'])
            - datetime.fromisoformat(episode['t_enter'])).total_seconds()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()
    day = args.date

    episodes = [e for e in load('episodes.jsonl') if e['t_enter'].startswith(day)]
    gates = [g for g in load('gate_log.jsonl') if g.get('ts', '').startswith(day)]
    if not episodes:
        print(f'No episodes for {day}.')
        return

    import movement_tracker as mt
    movements = mt.annotate(mt.build_movements(episodes), day)

    timetable = json.loads((APP_DATA / 'timetable2026.json').read_text())
    entry = timetable['days'].get(day, {})
    services = (timetable['patterns'][entry['pattern']]['services']
                if entry.get('kind') == 'service' else [])

    first = min(e['t_enter'] for e in episodes)[11:16]
    last = max(e['t_enter'] for e in episodes)[11:16]
    print(f'{day} · {first} to {last}\n')

    # --- gate ------------------------------------------------------------
    kinds = Counter(g['kind'] for g in gates)
    opened, wasted = kinds.get('gate', 0), kinds.get('false_gate', 0)
    if opened:
        print(f'Gate      {opened} opened, {wasted} found nothing '
              f'({wasted / opened:.0%} wasted)')
    print(f'Errors    {kinds.get("error", 0)}'
          + (f", {sum(1 for g in gates if g.get('challenge'))} bot challenges"
             if any(g.get('challenge') for g in gates) else ''))

    # --- detections against movements -------------------------------------
    matched = sum(1 for m in movements if m.get('scheduled'))
    print(f'\nDetections {len(episodes)}  ->  movements {len(movements)} '
          f'({matched} matched to a service, {len(movements) - matched} not)')

    # Repeat sightings of stabled stock are the main reason those two
    # numbers differ, and they are worth naming rather than averaging away.
    per_camera = Counter(e['camera'] for e in episodes)
    print('\nBusiest cameras, and how much of it is one thing sitting still:')
    for camera, count in per_camera.most_common(5):
        mine = [e for e in episodes if e['camera'] == camera]
        brief = [e for e in mine if (duration_s(e) or 0) < 120]
        low = [e for e in mine if (e.get('peak_conf') or 1) < 0.7]
        note = ''
        if count >= 8 and len(brief) / count > 0.6:
            note = f'  <-- {len(brief)} under 2 min, {len(low)} below 70% confident'
        print(f'  {camera:<28} {count:>3}{note}')

    # --- coverage ---------------------------------------------------------
    if services:
        # Only workings that have actually departed by the last sighting:
        # counting against the whole day mid-morning makes coverage look
        # far worse than it is.
        cutoff = last
        started = [s for s in services
                   if (s['stops'][0].get('d') or s['stops'][0].get('a') or '') <= cutoff]
        seen = {m['scheduled']['booked_departure'] for m in movements
                if m.get('scheduled')}
        print(f'\nService   {len(started)} of {len(services)} booked workings '
              f'had departed by {cutoff}; {len(seen)} of those were seen')
        missed = [s for s in started
                  if (s['stops'][0].get('d') or s['stops'][0].get('a')) not in seen]
        if missed:
            print('          not seen at all: ' + ', '.join(
                f"{m['stops'][0].get('d') or m['stops'][0].get('a')} "
                f"{m['direction']}" for m in missed))

    # --- what claims to be unscheduled ------------------------------------
    odd = [m for m in movements if not m.get('scheduled')]
    if odd:
        print(f'\nNot in the timetable ({len(odd)}):')
        for m in odd:
            lone = ' — single sighting, so nothing corroborates it' \
                if m['sightings'] < 2 else ''
            print(f"  {m['first_seen']}-{m['last_seen']} {m['from']}->{m['to']} "
                  f"{m['direction']}, {m['sightings']} sightings{lone}")

    # --- direction --------------------------------------------------------
    labelled = Counter(e.get('direction') for e in episodes)
    unclear = labelled.get('unclear', 0) + labelled.get(None, 0)
    print(f'\nDirection {len(episodes) - unclear} of {len(episodes)} sightings '
          f'carry one; {unclear} unclear')
    print('          run audit_directions.py to check those labels against '
          'the locomotives read')


if __name__ == '__main__':
    main()
