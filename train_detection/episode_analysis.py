"""Load watcher episodes and match them to the scraped WSR timetable.

An episode that matches a scheduled service confirms the timetable; a
confirmed episode with no match is the special-train signal.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

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


def match_episode(episode: dict) -> dict:
    """Return the episode annotated with its best timetable match (or None)."""
    station = CAMERA_STATIONS[episode['camera']]
    entered = datetime.fromisoformat(episode['t_enter'])
    calls = _scheduled_calls(entered.strftime('%Y-%m-%d'), station)

    best, best_gap = None, timedelta(minutes=MATCH_TOLERANCE_MIN)
    for call in calls:
        hh, mm = map(int, call['time'].split(':'))
        scheduled = entered.replace(hour=hh, minute=mm, second=0)
        gap = abs(scheduled - entered)
        direction_ok = (episode.get('direction') in (None, 'unclear')
                        or episode['direction'] == call['direction'])
        if gap <= best_gap and direction_ok:
            best, best_gap = call, gap
    return {
        **episode,
        'station': station,
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
