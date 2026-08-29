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

from train_tracker import (LINE, SEGMENTS, _hhmm, _station_coords, interpolate,
                           load_runs, observation_of, position_at, scheduled_at)

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
STALE_AFTER_MIN = 20.0          # an unscheduled movement unseen this long is lost:
                                # extrapolating further invents a position
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


# --------------------------------------------------------------------------
# Position — works for scheduled and unscheduled movements alike
# --------------------------------------------------------------------------

def movement_position(movement: dict, when: datetime, date_key: str) -> dict | None:
    """Where a movement is at `when`.

    A scheduled movement rides its booked timeline shifted by the delay it
    was last measured at. An unscheduled one has no timetable to lean on,
    so its position is extrapolated from its own observed speed — which is
    the whole point of tracking movements rather than runs.
    """
    clock = when.hour * 60 + when.minute + when.second / 60
    chain = movement.get('_chain')
    if not chain:
        return None
    first, last = chain[0], chain[-1]

    scheduled = movement.get('scheduled')
    if scheduled:
        for run in load_runs(date_key):
            if _hhmm(run['timeline'][0][1]) != scheduled['booked_departure']:
                continue
            tracked = {'_run': run, 'delay_min': scheduled['delay_end_min']}
            return position_at(tracked, when)

    # unscheduled: extrapolate along the line at the movement's own speed,
    # but only briefly — with no timetable to fall back on, a movement not
    # seen for a while has simply been lost
    speed = movement.get('avg_mph')
    if not speed or clock < first['clock']:
        return None
    since_seen = clock - last['clock']
    if not (0 <= since_seen <= STALE_AFTER_MIN):
        return None
    elapsed_h = since_seen / 60
    travelled = speed * elapsed_h
    heading = 1 if movement['direction'] == 'northbound' else -1
    index = LINE.index(last['station'])
    remaining = travelled
    while 0 <= index + heading < len(LINE):
        a, b = LINE[index], LINE[index + heading]
        seg = SEGMENTS.get((a, b)) or SEGMENTS.get((b, a))
        hop = (seg['length_m'] / 1609.34) if seg else 0.0
        if remaining <= hop or hop == 0:
            fraction = (remaining / hop) if hop else 0.0
            return {'state': 'running (unscheduled)', 'at': None,
                    'segment': [a, b], 'progress': round(fraction, 3),
                    'coords': interpolate(a, b, fraction),
                    'next': b, 'eta': None, 'extrapolated': True}
        remaining -= hop
        index += heading
    terminus = LINE[0 if heading < 0 else -1]
    return {'state': 'reached terminus (unscheduled)', 'at': terminus,
            'segment': None, 'progress': 1.0,
            'coords': _station_coords(terminus), 'next': None, 'eta': None,
            'extrapolated': True}


def live(episodes: list[dict], when: datetime | None = None,
         date_key: str = '2026-08-29') -> list[dict]:
    """Every movement currently on the line, scheduled or not."""
    when = when or datetime.now()
    movements = build_movements(episodes)
    annotated = annotate(movements, date_key)
    out = []
    for movement, record in zip(movements, annotated):
        record['_chain'] = movement['_chain']
        position = movement_position(record, when, date_key)
        if not position or position['state'].startswith('arrived'):
            continue
        record.pop('_chain', None)
        record['position'] = position
        record['confident'] = movement['sightings'] >= 2
        out.append(record)

    # two movements matching one booked run are fragments of the same
    # train that failed to chain — keep the better-corroborated fragment
    best_for_run: dict[str, dict] = {}
    unscheduled = []
    for record in out:
        s = record.get('scheduled')
        if not s:
            unscheduled.append(record)
            continue
        key = s['booked_departure'] + s['serviceType']
        incumbent = best_for_run.get(key)
        if incumbent is None or record['sightings'] > incumbent['sightings']:
            best_for_run[key] = record
    return sorted(unscheduled + list(best_for_run.values()),
                  key=lambda r: r['first_seen'])
