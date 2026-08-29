#!/usr/bin/env python3
"""Transform scraped WSR calendar data into the web app's timetable JSON.

Inputs (scraped from https://www.west-somerset-railway.co.uk/calendar):
  - day_timetables_raw.json   per-day station/time tables for running days
  - calendar_colours_raw.json per-date calendar colour swatches
  - nonrunning_days_raw.json  closed/event-only day summaries and links

Output:
  - ../../app/wsr-railway-app/src/data/timetable2026.json

Timetable cell notation (from the site's own key):
  10 15 / 10:15  normal call
  10x28          calls, and trains cross at this station
  08//32         passes non-stop (photographic timing only) -> not a stop
  -              no call
  STOP / START   short working terminates/starts (no time given)
  x              crosses without a public call -> not a stop
"""

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).parent
OUT_PATH = HERE / '../../app/wsr-railway-app/src/data/timetable2026.json'

STATION_CODES = OrderedDict([
    ('Norton Fitzwarren', 'NF'),
    ('Bishops Lydeard', 'BL'),
    ('Crowcombe Heathfield', 'CH'),
    ('Stogumber', 'STO'),
    ('Williton', 'WIL'),
    ('Doniford Halt (R)', 'DON'),
    ('Doniford Halt', 'DON'),
    ('Watchet', 'WAT'),
    ('Washford', 'WAS'),
    ('Blue Anchor', 'BA'),
    ('Dunster', 'DUN'),
    ('Minehead', 'MIN'),
])
# Order along the line, Bishops Lydeard end first
LINE_ORDER = ['NF', 'BL', 'CH', 'STO', 'WIL', 'DON', 'WAT', 'WAS', 'BA', 'DUN', 'MIN']

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
    'december': 12,
}

COLOUR_FAMILIES = {
    'rgb(185, 46, 42)': 'red',
    'rgb(61, 117, 237)': 'blue',
    'rgb(240, 125, 10)': 'orange',
    'rgb(237, 227, 92)': 'yellow',
    'rgb(255, 247, 92)': 'yellow',
    'rgb(255, 234, 0)': 'yellow',
    'rgb(137, 81, 41)': 'brown',
    'rgb(154, 6, 249)': 'purple',
    'rgb(72, 115, 29)': 'green',
    'rgb(222, 219, 219)': 'none',
    'rgb(209, 209, 209)': 'none',
}

TIME_RE = re.compile(r'^(\d{1,2})\s*(//|[x:\s])\s*(\d{2})$')

# The site names 12 August's one-off reduced service after its date
# ("12.08 - Timetable 2026"); give it a name consistent with the others.
TITLE_OVERRIDES = {
    '12.08 - Timetable 2026': 'Yellow Timetable (Reduced) 2026',
}


def modal_id_to_date(modal_id: str) -> str:
    month_name, day = modal_id.rsplit('-', 1)
    month = MONTHS[month_name]
    # The scraped calendar spans Aug 2026 - Jan 2027
    year = 2027 if month == 1 else 2026
    return f'{year}-{month:02d}-{int(day):02d}'


def title_to_family(title: str, colour_family: str | None) -> str:
    t = title.lower()
    for family in ('red', 'blue', 'orange', 'yellow', 'brown'):
        if re.search(rf'\b{family}\b', t):  # word boundary: "reduced" must not match "red"
            return family
    if '12.08' in t:
        return 'yellow'
    if 'christmas' in t:
        return 'green'
    if any(k in t for k in ('diesels @', 'forties', 'steam weekend', 'gala', 'event')):
        return 'purple'
    return colour_family or 'purple'


def parse_cell(raw: str):
    """Return (time or None, crosses: bool). None means no public call."""
    raw = raw.strip()
    if not raw or raw in {'-', '–', 'x', 'X', 'STOP', 'START'}:
        return None, False
    m = TIME_RE.match(raw)
    if not m:
        return None, False
    hours, sep, minutes = m.groups()
    if sep == '//':
        return None, False  # passes non-stop
    return f'{int(hours):02d}:{minutes}', sep in ('x', 'X')


def direction_of(codes: list[str]) -> str:
    first, last = LINE_ORDER.index(codes[0]), LINE_ORDER.index(codes[-1])
    return 'NB' if last > first else 'SB'


def parse_service_table(table: list[list[str]]):
    """Parse one direction's table into a list of services."""
    station_rows = []      # (code, cells)
    header_types = None    # from a 'Station' header row
    loco_row = None
    n_cols = max(len(r) for r in table)

    # Platform rows attach to the nearest station row above (else below)
    platforms = {}         # station-row index -> cells
    pending_platform = None
    for row in table:
        label = row[0].strip() if row else ''
        cells = row[1:] + [''] * (n_cols - len(row))
        if label == 'Station':
            header_types = cells
        elif label in STATION_CODES:
            station_rows.append((STATION_CODES[label], cells))
            if pending_platform is not None:
                platforms[len(station_rows) - 1] = pending_platform
                pending_platform = None
        elif label == 'Platform':
            if station_rows:
                platforms[len(station_rows) - 1] = cells
            else:
                pending_platform = cells
        elif label == 'Train Loco':
            loco_row = cells

    if not station_rows:
        return []

    services = []
    for col in range(n_cols - 1):
        entries = []  # (code, time, crosses, platform)
        for idx, (code, cells) in enumerate(station_rows):
            time, crosses = parse_cell(cells[col] if col < len(cells) else '')
            if time is None:
                continue
            platform_cells = platforms.get(idx)
            platform = None
            if platform_cells and col < len(platform_cells):
                p = platform_cells[col].strip()
                platform = p if p and p != '-' else None
            entries.append([code, time, crosses, platform])

        if len(entries) < 2:
            continue

        # Merge consecutive duplicate stations (arrival row + departure row)
        merged = []
        for e in entries:
            if merged and merged[-1][0] == e[0]:
                merged[-1] = [e[0], merged[-1][1], e[1], e[2] or merged[-1][3],
                              e[3] or merged[-1][4]]
            else:
                merged.append([e[0], e[1], None, e[2], e[3]])
        # merged entries: [code, timeA, timeB or None, crosses, platform]

        service_type = 'Diesel'
        if header_types and col < len(header_types) and header_types[col].strip():
            h = header_types[col].strip()
            service_type = 'DMU' if 'DMU' in h else ('Steam' if 'Steam' in h else 'Diesel')
        elif loco_row and col < len(loco_row):
            l = loco_row[col].strip()
            if 'steam' in l.lower():
                service_type = 'Steam'
            elif 'dmu' in l.lower():
                service_type = 'DMU'

        loco = None
        if loco_row and col < len(loco_row) and loco_row[col].strip() not in ('', 'Steam'):
            loco = loco_row[col].strip()

        codes = [m[0] for m in merged]
        stops = []
        for i, (code, time_a, time_b, crosses, platform) in enumerate(merged):
            arrival = None if i == 0 else time_a
            departure = None if i == len(merged) - 1 else (time_b or time_a)
            if i == len(merged) - 1 and time_b:
                arrival = time_b
            stop = {'c': code, 'a': arrival, 'd': departure}
            if crosses:
                stop['x'] = True
            if platform:
                stop['p'] = platform
            stops.append(stop)

        services.append({
            'direction': direction_of(codes),
            'serviceType': service_type,
            'loco': loco,
            'stops': stops,
        })
    return services


def main():
    day_tables = json.loads((HERE / 'day_timetables_raw.json').read_text())
    colours = json.loads((HERE / 'calendar_colours_raw.json').read_text())
    nonrunning = json.loads((HERE / 'nonrunning_days_raw.json').read_text())

    patterns = {}
    days = {}

    for modal_id, day in sorted(day_tables.items(), key=lambda kv: modal_id_to_date(kv[0])):
        date = modal_id_to_date(modal_id)
        title = re.sub(r'\s*-\s*\d+(st|nd|rd|th).*$', '', day['title']).strip()
        title = TITLE_OVERRIDES.get(title, title)
        colour = colours.get(date, {}).get('colour')
        family = title_to_family(title, COLOUR_FAMILIES.get(colour))

        services = []
        for table in day['tables']:
            if table and table[0] and table[0][0].strip() == 'Key':
                continue
            services.extend(parse_service_table(table))
        if not services:
            days[date] = {'kind': 'closed'}
            continue

        digest = hashlib.sha1(
            json.dumps(services, sort_keys=True).encode()).hexdigest()[:8]
        pattern_id = f'{family}-{digest}'
        if pattern_id not in patterns:
            patterns[pattern_id] = {
                'family': family,
                'title': title,
                'services': services,
            }
        days[date] = {'kind': 'service', 'pattern': pattern_id}
        if day.get('pdf'):
            days[date]['pdf'] = day['pdf']

    # Non-running days: closed, or event-only (Christmas etc.)
    for modal_id, info in nonrunning.items():
        date = modal_id_to_date(modal_id)
        if date in days:
            continue
        colour = colours.get(date, {}).get('colour')
        family = COLOUR_FAMILIES.get(colour, 'none')
        if family == 'none':
            days[date] = {'kind': 'closed'}
        else:
            events = sorted({
                url.rstrip('/').split('/')[-1].replace('-', ' ').title()
                for url in info.get('events', [])
            })
            days[date] = {'kind': 'event', 'family': family, 'events': events}

    # Any remaining coloured calendar dates without modal content
    for date, info in colours.items():
        if date in days:
            continue
        family = COLOUR_FAMILIES.get(info['colour'], 'none')
        days[date] = {'kind': 'closed'} if family == 'none' else {
            'kind': 'event', 'family': family, 'events': []}

    out = {
        'source': 'https://www.west-somerset-railway.co.uk/calendar',
        'scraped': '2026-08-27',
        'patterns': patterns,
        'days': dict(sorted(days.items())),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=1))

    # Summary
    from collections import Counter
    kinds = Counter(v['kind'] for v in days.values())
    print(f'patterns: {len(patterns)}, days: {len(days)}, kinds: {dict(kinds)}')
    for pid, p in patterns.items():
        nb = sum(1 for s in p['services'] if s['direction'] == 'NB')
        sb = len(p['services']) - nb
        used = sum(1 for d in days.values() if d.get('pattern') == pid)
        print(f'  {pid}: "{p["title"]}" {nb} NB + {sb} SB, used {used} day(s)')


if __name__ == '__main__':
    main()
