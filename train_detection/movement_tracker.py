"""Track physical train movements, whether or not they are timetabled.

`train_tracker` is timetable-first: it asks which booked run explains a
sighting, so an unscheduled train has nothing to be assigned to and is
discarded. This module inverts that.

A movement is built from physics alone — sightings are chained when the
gap between two cameras is a plausible transit for the real distance
between them, in a consistent direction, with a compatible identity if
one is known. Only afterwards is the movement compared to the timetable:

    movement + matching run   -> a scheduled service, with its delay
    movement + no run         -> an unscheduled working, still tracked

That makes light engines, empty stock, charters and specials first-class
citizens rather than residue. Identity (traction type now, class and
number once classification lands) is optional but tightens chaining
sharply: two Class 33s an hour apart are ambiguous by timing alone and
unambiguous by number.
"""

from datetime import datetime
from pathlib import Path
from statistics import median

from train_tracker import (CAMERA_NODES, CAMERA_OFFSET_MIN, LINE, SEGMENTS,
                           _hhmm, load_runs, observation_of, scheduled_at)

HERE = Path(__file__).parent

MIN_SPEED_MPH = 10.0    # slower than this and it is not a through movement
MAX_SPEED_MPH = 30.0    # line limit is 25; allow measurement slack
DWELL_ALLOWANCE_MIN = 6.0    # station calls between two cameras
MAX_MOVEMENT_MIN = 100.0     # end to end is ~80 min; longer is two movements
OCCUPANCY_MERGE_MIN = 15.0   # repeat sightings at one camera = one occupancy
# Delay accumulates along a journey — today's 10:15 steam left 10 min down
# and reached Blue Anchor 25 down — so the tolerance is on how much delay
# may GROW across a movement, not on it being constant.
MATCH_TOLERANCE_MIN = 22.0   # movement vs booked run
MAX_PLAUSIBLE_DELAY_MIN = 35.0
MAX_PLAUSIBLE_EARLY_MIN = 6.0   # trains do not leave before their booked time
EARLY_PENALTY = 3.0


def distance_miles(a: str, b: str) -> float:
    """Track distance between two stations, from the real segment lengths."""
    ia, ib = LINE.index(a), LINE.index(b)
    step = 1 if ib > ia else -1
    metres = 0.0
    for i in range(ia, ib, step):
        x, y = LINE[i], LINE[i + step]
        seg = SEGMENTS.get((x, y)) or SEGMENTS.get((y, x))
        metres += seg['length_m'] if seg else 0.0
    return metres / 1609.34


def transit_window(a: str, b: str) -> tuple[float, float]:
    """Plausible (min, max) minutes for a train to get from a to b."""
    miles = distance_miles(a, b)
    fastest = miles / MAX_SPEED_MPH * 60
    slowest = miles / MIN_SPEED_MPH * 60 + DWELL_ALLOWANCE_MIN
    return fastest, slowest


def _identity_compatible(x, y) -> bool:
    """Identities agree, or at least one is unknown."""
    if not x or not y:
        return True
    if x.get('number') and y.get('number'):
        return x['number'] == y['number']
    if x.get('traction') and y.get('traction'):
        return x['traction'] == y['traction']
    return True


def build_movements(episodes: list[dict],
                    identities: dict[str, dict] | None = None) -> list[dict]:
    """Chain sightings into physical movements, ignoring the timetable.

    A chain is grown forwards from its earliest sighting. The first link
    fixes the movement's direction and every later link must continue it:
    a train does not reverse mid-journey, so a chain that would double
    back is two movements, not one.

    identities maps an episode's t_enter to {'traction': ..., 'number': ...}
    when classification is available; chaining works without it.
    """
    identities = identities or {}
    observations = [o for o in (observation_of(e) for e in episodes) if o]
    for o in observations:
        entered = datetime.fromisoformat(o['episode']['t_enter'])
        o['clock'] = entered.hour * 60 + entered.minute + entered.second / 60
        o['identity'] = identities.get(o['episode']['t_enter'])
        o['index'] = LINE.index(o['station'])
    observations.sort(key=lambda o: o['clock'])
    observations = _merge_occupancies(observations)

    def plausible(previous, candidate, heading, head_clock):
        if candidate['station'] == previous['station']:
            return None
        step = candidate['index'] - previous['index']
        if heading == 'northbound' and step <= 0:
            return None
        if heading == 'southbound' and step >= 0:
            return None
        gap = candidate['clock'] - previous['clock']
        low, high = transit_window(previous['station'], candidate['station'])
        if not (low <= gap <= high):
            return None
        if candidate['clock'] - head_clock > MAX_MOVEMENT_MIN:
            return None
        if candidate['direction'] not in ('unclear', None) and \
                candidate['direction'] != heading:
            return None
        if not _identity_compatible(previous['identity'], candidate['identity']):
            return None
        expected = (low + high) / 2
        return abs(gap - expected)

    consumed = set()
    movements = []
    for head in observations:
        if id(head) in consumed:
            continue
        consumed.add(id(head))
        chain = [head]
        heading = head['direction'] if head['direction'] not in ('unclear', None) else None
        while True:
            best, best_cost = None, None
            for candidate in observations:
                if id(candidate) in consumed or candidate['clock'] <= chain[-1]['clock']:
                    continue
                for option in ([heading] if heading else ['northbound', 'southbound']):
                    cost = plausible(chain[-1], candidate, option, chain[0]['clock'])
                    if cost is not None and (best_cost is None or cost < best_cost):
                        best, best_cost = (candidate, option), cost
            if best is None:
                break
            candidate, option = best
            heading = option
            consumed.add(id(candidate))
            chain.append(candidate)
        movements.append(_summarise(chain))
    return sorted(movements, key=lambda m: m['first_seen'])


def _merge_occupancies(observations: list[dict]) -> list[dict]:
    """Collapse repeat sightings at one camera into a single observation.

    A rake standing in a terminus platform produces a detection every
    time the gate reopens; those are one occupancy of that station, not
    a series of separate trains, and left alone each one seeds a bogus
    movement. The earliest sighting of the group is kept as the arrival.
    """
    merged: list[dict] = []
    for obs in observations:
        previous = next((m for m in reversed(merged)
                         if m['camera'] == obs['camera']), None)
        if previous and obs['clock'] - previous['clock'] <= OCCUPANCY_MERGE_MIN:
            previous['repeat_sightings'] = previous.get('repeat_sightings', 1) + 1
            previous['clock_last'] = obs['clock']
            if obs['direction'] not in ('unclear', None) and \
                    previous['direction'] in ('unclear', None):
                previous['direction'] = obs['direction']
            continue
        merged.append(obs)
    return merged


def _summarise(chain: list[dict]) -> dict:
    first, last = chain[0], chain[-1]
    span = last['clock'] - first['clock']
    miles = distance_miles(first['station'], last['station'])
    heading = 'unclear'
    if len(chain) > 1:
        heading = 'northbound' if last['index'] > first['index'] else 'southbound'
    else:
        heading = first['direction']
    identity = next((o['identity'] for o in chain if o['identity']), None)
    return {
        'first_seen': _hhmm(first['clock']),
        'last_seen': _hhmm(last['clock']),
        'from': first['station'],
        'to': last['station'],
        'direction': heading,
        'sightings': len(chain),
        'miles': round(miles, 1),
        'avg_mph': round(miles / (span / 60), 1) if span > 0 and miles else None,
        'identity': identity,
        'observations': [
            {'at': o['episode']['t_enter'][11:19], 'camera': o['camera'],
             'station': o['station'], 'conf': o['episode']['peak_conf']}
            for o in chain
        ],
        '_chain': chain,
    }


def annotate(movements: list[dict], date_key: str) -> list[dict]:
    """Label each movement scheduled or unscheduled against the timetable."""
    runs = load_runs(date_key)
    out = []
    for movement in movements:
        chain = movement['_chain']
        best, best_cost = None, None
        for run in runs:
            if movement['direction'] not in ('unclear', None) and \
                    run['direction'] != movement['direction']:
                continue
            residuals = []
            for obs in chain:
                scheduled = scheduled_at(run, obs['station'])
                if scheduled is None:
                    residuals = None
                    break
                residuals.append(obs['observed'] - scheduled)
            if not residuals:
                continue
            spread = max(residuals) - min(residuals)
            delay = median(residuals)
            if spread > MATCH_TOLERANCE_MIN or not (
                    -MAX_PLAUSIBLE_EARLY_MIN <= delay <= MAX_PLAUSIBLE_DELAY_MIN):
                continue
            # a late train is ordinary; an early one is nearly always a
            # mis-match against the following service
            cost = spread + (delay * 0.1 if delay >= 0 else -delay * EARLY_PENALTY)
            if best_cost is None or cost < best_cost:
                best, best_cost = (run, delay, spread), cost
        record = {k: v for k, v in movement.items() if k != '_chain'}
        if best:
            run, delay, spread = best
            first_res = chain[0]['observed'] - scheduled_at(run, chain[0]['station'])
            last_res = chain[-1]['observed'] - scheduled_at(run, chain[-1]['station'])
            record['scheduled'] = {
                'booked_departure': _hhmm(run['timeline'][0][1]),
                'serviceType': run['serviceType'],
                'loco': run['loco'],
                'delay_min': round(delay, 1),
                'delay_start_min': round(first_res, 1),
                'delay_end_min': round(last_res, 1),
                'delay_gained_min': round(last_res - first_res, 1),
                'consistency_min': round(spread, 1),
            }
        else:
            record['scheduled'] = None
        out.append(record)
    return out


if __name__ == '__main__':
    from episode_analysis import load_episodes

    episodes = load_episodes()
    movements = annotate(build_movements(episodes), '2026-08-29')
    through = [m for m in movements if m['sightings'] > 1]
    print(f'{len(episodes)} episodes -> {len(movements)} movements '
          f'({len(through)} multi-camera)\n')
    for m in through:
        s = m['scheduled']
        tag = (f"SCHEDULED {s['booked_departure']} {s['serviceType']:<6} "
               f"{s['loco'] or '':<7} {s['delay_start_min']:+.0f}m->"
               f"{s['delay_end_min']:+.0f}m"
               if s else '*** UNSCHEDULED ***')
        print(f"{m['first_seen']}-{m['last_seen']} {m['from']}->{m['to']:<4} "
              f"{m['direction']:<10} {m['sightings']}x "
              f"{str(m['avg_mph']) + 'mph':<8} {tag}")
        for o in m['observations']:
            print(f"      {o['at']} {o['camera']}")
