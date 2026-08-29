"""One description of the cameras, for Python and for the web app.

The camera list had grown four copies — the capture module, the tracker's
station map, and three hardcoded maps in the React app, three of which
still listed six cameras after five more were added. Detections from the
newer cameras therefore rendered as raw ids and were missing from the
admin's per-camera counts entirely.

This module composes the existing sources rather than replacing them, so
there is still exactly one place that knows a camera's YouTube id and one
that knows which station it watches. What it adds is the presentation
layer — a display name, position along the line, and how far the hand
annotation has got — and it writes the whole lot out for the frontend.

    python3 camera_registry.py            # print the registry
    python3 camera_registry.py --write    # regenerate the app's copy
"""

import argparse
import json
from pathlib import Path

import track_geometry as tg
from train_tracker import CAMERA_NODES, LINE, STATION_NAMES
from wsr_live_capture import CALIBRATED, CAMERAS

HERE = Path(__file__).parent
APP_DATA = (HERE.parent / 'app' / 'wsr-railway-app' / 'src' / 'data'
            / 'cameras.json')

# Where a camera's own name needs to differ from its station's — two views
# of one station, or a location that is not a station at all.
DISPLAY_NAMES = {
    'crowcombe_heathfield': 'Crowcombe Heathfield',
    'crowcombe_heathfield_2': 'Crowcombe Heathfield, second view',
    'williton': 'Williton',
    'williton_2': 'Williton, second view',
    'watchet_1': 'Watchet, station',
    'watchet_visitor_centre': 'Watchet, visitor centre',
    'blue_anchor': 'Blue Anchor',
    'blue_anchor_2': 'Blue Anchor, second view',
    'minehead_seaward_crossing': 'Seaward Crossing',
    'minehead_station': 'Minehead',
    'bishops_lydeard': 'Bishops Lydeard',
}


def annotation_of(camera: str) -> dict:
    """How far hand annotation has got at this camera."""
    roads = tg.tracks_of(camera)
    mask = tg.exclusion_mask(camera, 854, 480)
    return {
        'roads': len(roads),
        'platforms': len(tg.regions_of(camera, 'platform')),
        'occluders': len(tg.regions_of(camera, 'occluder')),
        'blockedShare': round(float((mask > 0).mean()), 3),
        'orientationKnown': tg.minehead_end_known(camera),
        'ready': bool(roads),
    }


def registry() -> list[dict]:
    """Every camera, ordered Bishops Lydeard end first."""
    entries = []
    for camera, video_id in CAMERAS.items():
        station = CAMERA_NODES.get(camera)
        entries.append({
            'id': camera,
            'name': DISPLAY_NAMES.get(camera, camera.replace('_', ' ').title()),
            'station': station,
            'stationName': STATION_NAMES.get(station) if station else None,
            'lineIndex': LINE.index(station) if station in LINE else None,
            'videoId': video_id,
            'directionValidated': camera in CALIBRATED,
            'annotation': annotation_of(camera),
        })
    entries.sort(key=lambda e: (e['lineIndex'] is None,
                                e['lineIndex'] or 0, e['id']))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true',
                        help="regenerate the web app's cameras.json")
    args = parser.parse_args()

    entries = registry()
    print(f"{'camera':<28} {'station':>8} {'roads':>6} {'plat':>5} "
          f"{'blocked':>8} {'direction':>10}")
    for entry in entries:
        note = entry['annotation']
        print(f"{entry['id']:<28} {entry['station'] or '—':>8} "
              f"{note['roads']:>6} {note['platforms']:>5} "
              f"{note['blockedShare']:>7.0%} "
              f"{('validated' if entry['directionValidated'] else 'from order'):>10}")

    ready = sum(e['annotation']['ready'] for e in entries)
    print(f'\n{ready} of {len(entries)} cameras have traced track')

    if args.write:
        APP_DATA.parent.mkdir(parents=True, exist_ok=True)
        APP_DATA.write_text(json.dumps(entries, indent=1) + '\n')
        print(f'wrote {APP_DATA}')


if __name__ == '__main__':
    main()
