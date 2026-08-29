"""Track trains as entities moving along the line graph.

Point-matching each sighting to its nearest timetabled call breaks down
once services run late: a train 25 minutes down looks like the *next*
service running early. This module instead treats the line as a graph and
a timetabled service as a run travelling along it, then:

  1. builds the line graph (nodes = stations, edges = real geojson
     segments with lengths and polylines),
  2. assigns camera observations to whole runs rather than to individual
     calls, scoring each run by how consistently it explains them,
  3. estimates each run's delay from its observations, and
  4. interpolates position at any instant -> segment, progress, lat/lng.

Output matches the web app's TrainLocation model, so tracked positions
can drive the existing route map and track map directly.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

HERE = Path(__file__).parent
APP_DATA = HERE / '../app/wsr-railway-app/src/data'

# Line order from the Bishops Lydeard (Taunton) end
LINE = ['NF', 'BL', 'CH', 'STO', 'WIL', 'DON', 'WAT', 'WAS', 'BA', 'DUN', 'MIN']

STATION_NAMES = {
    'NF': 'Norton Fitzwarren', 'BL': 'Bishops Lydeard',
    'CH': 'Crowcombe Heathfield', 'STO': 'Stogumber', 'WIL': 'Williton',
    'DON': 'Doniford Halt', 'WAT': 'Watchet', 'WAS': 'Washford',
    'BA': 'Blue Anchor', 'DUN': 'Dunster', 'MIN': 'Minehead',
}
NAME_TO_CODE = {v: k for k, v in STATION_NAMES.items()}

# Where each camera observes. Cameras sitting between stations record the
# segment they overlook rather than a node.
CAMERA_NODES = {
    'bishops_lydeard': 'BL',
    'crowcombe_heathfield': 'CH',
    'watchet_visitor_centre': 'WAT',
    'blue_anchor': 'BA',
    'minehead_station': 'MIN',
    'minehead_seaward_crossing': 'DUN',  # observes the Dunster–Minehead approach
}
CAMERA_OFFSET_MIN = {'minehead_seaward_crossing': 5.0}  # ~5 min after Dunster

ASSIGN_WINDOW_MIN = 35      # a run may be considered for a sighting this far off
CONSISTENCY_SPREAD_MIN = 9  # observations of one run should agree within this
EARLY_PENALTY = 3.0         # trains run late, not early: weight early residuals
                            # heavily so a late service keeps its own sightings
                            # instead of being read as the next one running early


# --------------------------------------------------------------------------
# Line graph
# --------------------------------------------------------------------------

def load_segments() -> dict:
    """{(from_code, to_code): {'length_m', 'coords'}} for each real segment."""
    raw = json.loads((APP_DATA / 'segments.geojson').read_text())
    segments = {}
    for feature in raw['features']:
        props = feature['properties']
        a = NAME_TO_CODE.get(props['from'])
        b = NAME_TO_CODE.get(props['to'])
        if not a or not b:
            continue
        segments[(a, b)] = {
            'length_m': props.get('length_m_approx', 0.0),
            'coords': feature['geometry']['coordinates'],  # [lng, lat] pairs
        }
    return segments


SEGMENTS = load_segments()


def segment_between(a: str, b: str):
    """Segment geometry for an adjacent pair, in the a->b direction."""
    if (a, b) in SEGMENTS:
        return SEGMENTS[(a, b)], False
    if (b, a) in SEGMENTS:
        return SEGMENTS[(b, a)], True
    return None, False


def interpolate(a: str, b: str, fraction: float):
    """Lat/lng a given fraction of the way from a to b.

    a and b need not be adjacent: a service that skips intermediate
    stations still travels through them, so walk the real segments in
    between and distribute the fraction by their true lengths.
    """
    ia, ib = LINE.index(a), LINE.index(b)
    step = 1 if ib > ia else -1
    hops = [(LINE[i], LINE[i + step]) for i in range(ia, ib, step)]
    if len(hops) > 1:
        lengths = []
        for x, y in hops:
            seg, _ = segment_between(x, y)
            lengths.append(seg['length_m'] if seg else 0.0)
        total = sum(lengths) or 1.0
        target = max(0.0, min(1.0, fraction)) * total
        walked = 0.0
        for (x, y), length in zip(hops, lengths):
            if walked + length >= target:
                inner = (target - walked) / length if length else 0.0
                return interpolate(x, y, inner)
            walked += length
        return interpolate(*hops[-1], 1.0)

    seg, reversed_ = segment_between(a, b)
    if not seg:
        return None
    coords = list(reversed(seg['coords'])) if reversed_ else seg['coords']
    if len(coords) < 2:
        return None
    # cumulative distance in coordinate space is close enough at this scale
    spans = []
    for i in range(len(coords) - 1):
        (x1, y1), (x2, y2) = coords[i], coords[i + 1]
        spans.append(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
    total = sum(spans) or 1.0
    target = max(0.0, min(1.0, fraction)) * total
    walked = 0.0
    for i, span in enumerate(spans):
        if walked + span >= target:
            t = (target - walked) / span if span else 0.0
            (x1, y1), (x2, y2) = coords[i], coords[i + 1]
            return {'lat': y1 + (y2 - y1) * t, 'lng': x1 + (x2 - x1) * t}
        walked += span
    lng, lat = coords[-1]
    return {'lat': lat, 'lng': lng}


# --------------------------------------------------------------------------
# Runs (a timetabled service on a date)
# --------------------------------------------------------------------------

def load_runs(date_key: str) -> list[dict]:
    """Timetabled services for a date, as runs with an ordered call list."""
    data = json.loads((APP_DATA / 'timetable2026.json').read_text())
    day = data['days'].get(date_key)
    if not day or day.get('kind') != 'service':
        return []
    runs = []
    for index, service in enumerate(data['patterns'][day['pattern']]['services']):
        timeline = []  # (station, minutes-since-midnight, is_pass)
        for stop in service['stops']:
            when = stop['a'] or stop['d']
            if when:
                timeline.append((stop['c'], _minutes(when), False))
        for p in service.get('passes', []):
            timeline.append((p['c'], _minutes(p['t']), True))
        # order along the direction of travel
        forward = service['direction'] == 'NB'
        timeline.sort(key=lambda e: LINE.index(e[0]), reverse=not forward)
        if len(timeline) < 2:
            continue
        runs.append({
            'run_id': f"{date_key}_{service['direction']}_{timeline[0][1]:04d}_{index}",
            'direction': 'northbound' if forward else 'southbound',
            'serviceType': service['serviceType'],
            'loco': service.get('loco'),
            'timeline': timeline,
            'origin': timeline[0][0],
            'destination': timeline[-1][0],
        })
    return runs


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


def _hhmm(minutes: float) -> str:
    minutes = int(round(minutes))
    return f'{minutes // 60 % 24:02d}:{minutes % 60:02d}'


def scheduled_at(run: dict, station: str):
    """Scheduled minutes at a station on this run, or None if not served."""
    for code, when, _is_pass in run['timeline']:
        if code == station:
            return when
    return None


# --------------------------------------------------------------------------
# Assignment: observations -> runs
# --------------------------------------------------------------------------

def observation_of(episode: dict) -> dict | None:
    """An episode reduced to (station, observed minutes, direction)."""
    camera = episode['camera']
    node = CAMERA_NODES.get(camera)
    if not node:
        return None
    entered = datetime.fromisoformat(episode['t_enter'])
    observed = entered.hour * 60 + entered.minute + entered.second / 60
    observed -= CAMERA_OFFSET_MIN.get(camera, 0.0)
    return {
        'episode': episode,
        'camera': camera,
        'station': node,
        'observed': observed,
        'direction': episode.get('direction', 'unclear'),
        'date_key': entered.strftime('%Y-%m-%d'),
    }


def assign(episodes: list[dict]):
    """Assign observations to runs, then estimate each run's delay.

    Three rules keep terminus shunts and platform dwells from polluting a
    run, which naive nearest-call matching cannot do:

      one per station  a run passes a station once, so competing sightings
                       at the same station keep only the closest — a rake
                       sitting in a platform is one call, not six;
      sequence order   a run's sightings must progress along the line in
                       its direction of travel;
      outlier reject   a sighting whose residual disagrees with the run's
                       median delay is released rather than dragging it.

    Released sightings are returned as unassigned — those are the shunts,
    light engines and genuinely unscheduled movements.
    """
    observations = [o for o in (observation_of(e) for e in episodes) if o]
    if not observations:
        return [], []
    runs = {}
    for date_key in {o['date_key'] for o in observations}:
        for run in load_runs(date_key):
            runs[run['run_id']] = run

    delays: dict[str, float] = {}
    buckets: dict[str, list] = {}

    for _iteration in range(3):
        candidates: dict[str, list] = {}
        for obs in observations:
            best, best_cost = None, None
            for run in runs.values():
                if obs['direction'] not in ('unclear', None) and \
                        obs['direction'] != run['direction']:
                    continue
                scheduled = scheduled_at(run, obs['station'])
                if scheduled is None:
                    continue
                predicted = scheduled + delays.get(run['run_id'], 0.0)
                residual = obs['observed'] - predicted
                if abs(residual) > ASSIGN_WINDOW_MIN:
                    continue
                # asymmetric: being seen before the booked time is far less
                # plausible than being seen after it
                cost = residual if residual >= 0 else -residual * EARLY_PENALTY
                if best_cost is None or cost < best_cost:
                    best, best_cost = run, cost
            if best:
                candidates.setdefault(best['run_id'], []).append((obs, best_cost))

        buckets = {}
        for run_id, entries in candidates.items():
            run = runs[run_id]
            # rule 1: one observation per station, the closest
            by_station: dict[str, tuple] = {}
            for obs, cost in entries:
                prev = by_station.get(obs['station'])
                if prev is None or cost < prev[1]:
                    by_station[obs['station']] = (obs, cost)
            kept = [obs for obs, _ in by_station.values()]

            # rule 2: sightings must progress along the line in travel order
            forward = run['direction'] == 'northbound'
            kept.sort(key=lambda o: o['observed'])
            ordered, last_index = [], None
            for obs in kept:
                index = LINE.index(obs['station'])
                if last_index is None or \
                        (index > last_index if forward else index < last_index):
                    ordered.append(obs)
                    last_index = index
            kept = ordered

            # rule 3: release sightings that disagree with the run's delay
            if kept:
                residuals = [o['observed'] - scheduled_at(run, o['station'])
                             for o in kept]
                centre = median(residuals)
                kept = [o for o, r in zip(kept, residuals)
                        if abs(r - centre) <= CONSISTENCY_SPREAD_MIN]
            if kept:
                buckets[run_id] = kept

        delays = {
            run_id: median([o['observed'] - scheduled_at(runs[run_id], o['station'])
                            for o in kept])
            for run_id, kept in buckets.items()
        }

    assigned_keys = {o['episode']['t_enter']
                     for kept in buckets.values() for o in kept}

    tracked = []
    for run_id, kept in buckets.items():
        run = runs[run_id]
        residuals = [o['observed'] - scheduled_at(run, o['station']) for o in kept]
        spread = max(residuals) - min(residuals) if len(residuals) > 1 else 0.0
        tracked.append({
            'run_id': run_id,
            'direction': run['direction'],
            'serviceType': run['serviceType'],
            'loco': run['loco'],
            'origin': run['origin'],
            'destination': run['destination'],
            'booked_departure': _hhmm(run['timeline'][0][1]),
            'delay_min': round(delays[run_id], 1),
            'observations': [
                {'camera': o['camera'], 'station': o['station'],
                 'at': o['episode']['t_enter'][11:19],
                 'booked': _hhmm(scheduled_at(run, o['station'])),
                 'residual_min': round(o['observed'] - scheduled_at(run, o['station']), 1)}
                for o in sorted(kept, key=lambda o: o['observed'])
            ],
            'corroboration': len(kept),
            'consistency_min': round(spread, 1),
            'confident': len(kept) >= 2 and spread <= CONSISTENCY_SPREAD_MIN,
            '_run': run,
        })

    unassigned = [o for o in observations
                  if o['episode']['t_enter'] not in assigned_keys]
    return sorted(tracked, key=lambda t: t['booked_departure']), unassigned


# --------------------------------------------------------------------------
# Position on the graph
# --------------------------------------------------------------------------

def position_at(tracked: dict, when: datetime) -> dict | None:
    """Where a tracked run is at a given time, in TrainLocation shape."""
    run = tracked['_run']
    delay = tracked['delay_min']
    now = when.hour * 60 + when.minute + when.second / 60
    effective = now - delay          # position on the booked timeline
    timeline = run['timeline']

    if effective < timeline[0][1]:
        return {'state': 'awaiting departure', 'at': timeline[0][0],
                'segment': None, 'progress': 0.0,
                'coords': _station_coords(timeline[0][0]),
                'next': timeline[0][0], 'eta': _hhmm(timeline[0][1] + delay)}
    if effective > timeline[-1][1]:
        return {'state': 'arrived', 'at': timeline[-1][0], 'segment': None,
                'progress': 1.0, 'coords': _station_coords(timeline[-1][0]),
                'next': None, 'eta': None}

    for i in range(len(timeline) - 1):
        (a, ta, _), (b, tb, _) = timeline[i], timeline[i + 1]
        if ta <= effective <= tb:
            span = tb - ta
            fraction = (effective - ta) / span if span else 0.0
            if fraction < 0.02:
                return {'state': 'at station', 'at': a, 'segment': None,
                        'progress': 0.0, 'coords': _station_coords(a),
                        'next': b, 'eta': _hhmm(tb + delay)}
            return {'state': 'running', 'at': None, 'segment': [a, b],
                    'progress': round(fraction, 3),
                    'coords': interpolate(a, b, fraction),
                    'next': b, 'eta': _hhmm(tb + delay)}
    return None


def _station_coords(code: str):
    for (a, b), seg in SEGMENTS.items():
        if a == code:
            lng, lat = seg['coords'][0]
            return {'lat': lat, 'lng': lng}
        if b == code:
            lng, lat = seg['coords'][-1]
            return {'lat': lat, 'lng': lng}
    return None


def live_positions(episodes: list[dict], when: datetime | None = None,
                   confident_only: bool = False):
    """Tracked runs with their position at `when` (default: now).

    Runs seen only once cannot be corroborated, and a run whose estimated
    delay is negative is almost certainly matched to the wrong service —
    both are marked `uncertain` so callers can down-weight or hide them.
    """
    when = when or datetime.now()
    tracked, unassigned = assign(episodes)
    out = []
    for t in tracked:
        pos = position_at(t, when)
        if not pos or pos['state'] == 'arrived':
            continue
        uncertain = (not t['confident']) or t['delay_min'] < -2
        if confident_only and uncertain:
            continue
        out.append({**{k: v for k, v in t.items() if k != '_run'},
                    'uncertain': uncertain, 'position': pos})
    return out, unassigned


if __name__ == '__main__':
    from episode_analysis import load_episodes

    episodes = load_episodes()
    tracked, unassigned = assign(episodes)
    print(f'{len(episodes)} episodes -> {len(tracked)} runs '
          f'({len(unassigned)} unassigned)\n')
    for t in tracked:
        flag = 'OK ' if t['confident'] else '   '
        print(f"{flag}{t['booked_departure']} {t['direction']:<10} "
              f"{t['serviceType']:<6} {t['loco'] or '':<7} "
              f"{t['origin']}->{t['destination']:<4} "
              f"delay {t['delay_min']:+5.1f}m  seen {t['corroboration']}x "
              f"(spread {t['consistency_min']}m)")
        for o in t['observations']:
            print(f"      {o['at']} {o['camera']:<26} booked {o['booked']} "
                  f"({o['residual_min']:+.1f}m)")
