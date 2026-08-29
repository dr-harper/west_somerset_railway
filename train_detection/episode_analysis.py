"""Load watcher episodes and match them to the scraped WSR timetable.

An episode that matches a scheduled service confirms the timetable; a
confirmed episode with no match is the special-train signal.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from gala_watcher import NORTHBOUND_VECTORS, UNRELIABLE_DRIFT_CAMERAS

HERE = Path(__file__).parent
EPISODES_PATH = HERE / 'episodes.jsonl'
TIMETABLE_PATH = HERE / '../app/wsr-railway-app/src/data/timetable2026.json'

# Camera -> station the detect zones cover
CAMERA_STATIONS = {
    'minehead_station': 'MIN',
    'minehead_seaward_crossing': 'MIN',   # approach to Minehead
    'blue_anchor': 'BA',
    'watchet_visitor_centre': 'WAT',
    'crowcombe_heathfield': 'CH',
    'bishops_lydeard': 'BL',
}

MATCH_TOLERANCE_MIN = 10


def load_episodes(path: Path = EPISODES_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _services_for_date(date_key: str) -> list[dict]:
    data = json.loads(Path(TIMETABLE_PATH).read_text())
    day = data['days'].get(date_key)
    if not day or day.get('kind') != 'service':
        return []
    return data['patterns'][day['pattern']]['services']


def _scheduled_calls(date_key: str, station: str) -> list[dict]:
    """Every scheduled call OR non-stop pass at a station."""
    calls = []
    for service in _services_for_date(date_key):
        direction = 'northbound' if service['direction'] == 'NB' else 'southbound'
        base = {'direction': direction,
                'serviceType': service['serviceType'],
                'loco': service.get('loco')}
        for stop in service['stops']:
            if stop['c'] == station and (stop['a'] or stop['d']):
                calls.append({**base, 'time': stop['a'] or stop['d'], 'passes': False})
        for p in service.get('passes', []):
            if p['c'] == station:
                calls.append({**base, 'time': p['t'], 'passes': True})
    return sorted(calls, key=lambda c: c['time'])


def _direction_from_drift(episode: dict) -> str:
    """Recompute direction from stored drift so vector corrections apply
    retrospectively to already-logged episodes."""
    if episode['camera'] in UNRELIABLE_DRIFT_CAMERAS:
        return 'unclear'   # let the movement's station order decide
    drift = episode.get('drift_px')
    if not drift:
        return episode.get('direction', 'unclear')
    magnitude = (drift[0] ** 2 + drift[1] ** 2) ** 0.5
    if magnitude < 30:
        return 'unclear'
    nx, ny = NORTHBOUND_VECTORS[episode['camera']]
    return 'northbound' if drift[0] * nx + drift[1] * ny > 0 else 'southbound'


def match_episode(episode: dict) -> dict:
    """Return the episode annotated with its best timetable match (or None).

    A call matches if it falls within the episode's occupancy span (plus
    tolerance either side) — long platform dwells cover their departures.
    """
    station = CAMERA_STATIONS[episode['camera']]
    entered = datetime.fromisoformat(episode['t_enter'])
    exited = datetime.fromisoformat(episode.get('t_exit', episode['t_enter']))
    direction = _direction_from_drift(episode)
    calls = _scheduled_calls(entered.strftime('%Y-%m-%d'), station)

    best, best_gap = None, timedelta(minutes=MATCH_TOLERANCE_MIN)
    for call in calls:
        hh, mm = map(int, call['time'].split(':'))
        scheduled = entered.replace(hour=hh, minute=mm, second=0)
        if scheduled < entered:
            gap = entered - scheduled
        elif scheduled > exited:
            gap = scheduled - exited
        else:
            gap = timedelta(0)  # call falls inside the occupancy span
        direction_ok = (direction in (None, 'unclear')
                        or direction == call['direction'])
        if gap <= best_gap and direction_ok:
            best, best_gap = call, gap
    return {
        **episode,
        'station': station,
        'direction': direction,
        'match': best,
        'match_gap_min': round(best_gap.total_seconds() / 60, 1) if best else None,
        'is_special': best is None,
    }


def match_all(episodes: list[dict] | None = None) -> list[dict]:
    return [match_episode(e) for e in (episodes or load_episodes())]


if __name__ == '__main__':
    matched = match_all()
    print(f'{len(matched)} episodes')
    for m in matched:
        tag = 'SPECIAL?' if m['is_special'] else \
            f"{m['match']['time']} {m['match']['serviceType']} ({m['match_gap_min']}m off)"
        print(f"{m['t_enter']} {m['camera']:<28} {m.get('direction', '?'):<11} -> {tag}")
