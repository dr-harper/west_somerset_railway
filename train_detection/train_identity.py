"""What was actually working each train, against what was booked.

A single still is a poor witness. An episode lasting a minute is mostly
coaches, and a photograph of coaches honestly answers "unsure" — so a
per-still reading is right far less often than it is confident. A
movement is the better unit: the same train seen at three or four
cameras gives three or four looks at it, and the leading vehicle is
visible in at least one.

The point of doing this is the disagreement. The timetable says a working
is Steam or Diesel, but cover changes: a booked steam turn runs behind a
diesel, a guest locomotive appears that no timetable knows about — 29/8
had GB Railfreight 66748 at Bishops Lydeard, which no amount of schedule
reading would predict. What is actually on the front can only come from
the picture, and where picture and timetable differ, the picture wins.

    python3 train_identity.py                # summarise the day
    python3 train_identity.py --disagreements
"""

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
CLASSIFICATIONS = HERE / 'classifications.json'
OUT_PATH = HERE / 'train_identities.json'

# A booked service type maps onto the traction we expect to see.
BOOKED_TO_TRACTION = {'Steam': 'steam', 'Diesel': 'diesel', 'DMU': 'dmu'}


def _vote(values: list[str]) -> tuple[str | None, int, int]:
    """Most common non-empty value, how many said it, how many spoke."""
    said = [v for v in values if v]
    if not said:
        return None, 0, 0
    value, count = Counter(said).most_common(1)[0]
    return value, count, len(said)


def identify(movement: dict, classifications: dict) -> dict:
    """Pool every classification behind one movement into one identity."""
    readings = [classifications[obs['at_iso']]
                for obs in movement.get('_observations', [])
                if obs.get('at_iso') in classifications]

    # 'unsure' is not a vote for anything: it means no traction was in
    # view, which several stills of coaches will say in chorus.
    traction, agree, spoke = _vote(
        [r['traction'] for r in readings if r.get('traction') != 'unsure'])
    number, number_agree, _ = _vote([r.get('number') for r in readings])
    train_class, _, _ = _vote([r.get('train_class') for r in readings])

    booked = movement.get('serviceType')
    expected = BOOKED_TO_TRACTION.get(booked) if booked else None
    return {
        'traction': traction,
        'traction_agreement': f'{agree}/{spoke}' if spoke else None,
        'number': number,
        'number_agreement': number_agree or None,
        'train_class': train_class,
        'stills_read': len(readings),
        'booked_serviceType': booked,
        # Only a disagreement when both are known: an unidentified
        # movement is a gap, not a contradiction.
        'disagrees_with_timetable': bool(
            traction and expected and traction != expected),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--disagreements', action='store_true',
                        help='only show where the picture and timetable differ')
    args = parser.parse_args()

    if not CLASSIFICATIONS.exists():
        print('No classifications yet — run python3 classify_trains.py')
        return
    classifications = json.loads(CLASSIFICATIONS.read_text())

    from episode_analysis import load_episodes
    from movement_tracker import annotate, build_movements

    episodes = load_episodes()
    date_key = episodes[0]['t_enter'][:10]
    movements = build_movements(episodes)
    records = annotate(movements, date_key)

    identities = []
    for movement, record in zip(movements, records):
        scheduled = record.get('scheduled') or {}
        merged = {
            **record,
            'serviceType': scheduled.get('serviceType'),
            '_observations': [
                {'at_iso': obs['episode']['t_enter']} for obs in movement['_chain']
            ],
        }
        identity = identify(merged, classifications)
        identities.append({
            'movement_id': (f"{date_key.replace('-', '')}_"
                            f"{record['first_seen'].replace(':', '')}_"
                            f"{record['from']}_{record['to']}"),
            'first_seen': record['first_seen'],
            'from': record['from'],
            'to': record['to'],
            **identity,
        })

    OUT_PATH.write_text(json.dumps(identities, indent=1))

    shown = [i for i in identities
             if not args.disagreements or i['disagrees_with_timetable']]
    print(f"{'time':<7} {'route':<10} {'seen':<8} {'number':<8} "
          f"{'class':<22} {'booked':<8} agreement")
    for item in shown:
        flag = '  <-- differs' if item['disagrees_with_timetable'] else ''
        print(f"{item['first_seen']:<7} "
              f"{item['from'] + '-' + item['to']:<10} "
              f"{item['traction'] or '—':<8} {item['number'] or '—':<8} "
              f"{(item['train_class'] or '—')[:21]:<22} "
              f"{item['booked_serviceType'] or '—':<8} "
              f"{item['traction_agreement'] or '—'}{flag}")

    identified = sum(1 for i in identities if i['traction'])
    numbered = sum(1 for i in identities if i['number'])
    differs = sum(1 for i in identities if i['disagrees_with_timetable'])
    print(f'\n{identified} of {len(identities)} movements have traction, '
          f'{numbered} carry a running number')
    print(f'{differs} disagree with what the timetable booked')
    print(f'wrote {OUT_PATH.name}')


if __name__ == '__main__':
    main()
