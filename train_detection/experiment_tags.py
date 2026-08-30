"""Do the proposed tags actually work? Tested against two days of episodes.

Five things worth knowing about a sighting that the pipeline does not
currently record. Each is prototyped here and judged against evidence
already on disk, so the answer is a measurement rather than an opinion.

  standing      did the train move, or is this the same stabled rake
                triggering the gate again? One train in the Williton loop
                produced twenty-five episodes on 30/8.
  length        how long the train is, in metres, from the detection box
                and the rail-gauge scale.
  light engine  a locomotive on its own, which is a shunt or a stock move
                rather than a service — and a likely explanation for
                several movements reported as unscheduled.
  speed         from pixel motion through the local scale. Checkable,
                because station-to-station timing gives a second estimate
                that shares none of the same inputs.
  headcode      the four characters on the front, which identify the
                working and are far larger than a cab-side number.

    python3 experiment_tags.py [--date 2026-08-30]
"""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

import track_geometry as tg

HERE = Path(__file__).parent

# Below this a path has not gone anywhere: measured on 30/8 the stabled
# Williton episodes travelled 0-3 px while real movements ran 650-2100.
STANDING_PX = 120

# A locomotive is roughly 15-20 m; anything longer is carrying something.
LIGHT_ENGINE_M = 26.0


def load_episodes(day: str | None) -> list[dict]:
    lines = (HERE / 'episodes.jsonl').read_text().splitlines()
    episodes = [json.loads(line) for line in lines if line.strip()]
    return [e for e in episodes if not day or e['t_enter'].startswith(day)]


def travelled_px(episode: dict) -> float | None:
    """Total distance the centroid covered, not where it ended up.

    Net drift cannot tell a stabled rake from one that arrived and then
    stood: both finish where they started. Path length can.
    """
    path = episode.get('path') or []
    if len(path) < 2:
        return None
    return sum(math.dist(a[1:], b[1:]) for a, b in zip(path, path[1:]))


def is_standing(episode: dict) -> bool | None:
    distance = travelled_px(episode)
    return None if distance is None else distance < STANDING_PX


def train_length_m(episode: dict) -> float | None:
    """Along-track distance between the two ends of the detection box.

    Measuring the box's pixel width and multiplying by the scale at its
    centre gives nonsense — it read every train on 30/8 as under 26 m,
    including five-coach rakes. A receding train's length runs along the
    rails, not across the image, and the scale changes over that span. So
    both ends are projected onto the track and the distance measured in
    arc length, integrating the scale as it goes.
    """
    boxes = episode.get('boxes') or {}
    best = None
    for record in boxes.values():
        width, height = record.get('width'), record.get('height')
        if not width or not height:
            continue
        sx, sy = 854 / width, 480 / height
        for detection in record.get('detections') or []:
            x1, y1, x2, y2 = detection['box']
            # The two ends of the box, each placed on the track it sits on
            ends = [((x1 * sx), ((y1 + y2) / 2 * sy)),
                    ((x2 * sx), ((y1 + y2) / 2 * sy))]
            placed = [tg.project(episode['camera'], point) for point in ends]
            if not all(placed) or placed[0]['track'] != placed[1]['track']:
                continue
            near, far = sorted(placed, key=lambda p: p['arc_px'])
            scales = [p['metres_per_px'] for p in (near, far) if p['metres_per_px']]
            if not scales:
                continue
            # mean of the two scales over the span they bracket
            metres = (far['arc_px'] - near['arc_px']) * (sum(scales) / len(scales))
            if best is None or metres > best:
                best = metres
    return best


def observed_speed(episode: dict) -> float | None:
    """Fastest sustained speed in frame, not the average over the episode.

    A train that runs in, stands for fourteen minutes and leaves averages
    close to nothing, which is true and useless. What the station-to-station
    figure can be compared against is how fast it was actually travelling,
    so take the quickest pair of consecutive path points.
    """
    path = episode.get('path') or []
    if len(path) < 2:
        return None
    best = None
    for a, b in zip(path, path[1:]):
        speed = tg.speed_mph(episode['camera'], [a, b])
        if speed is not None and (best is None or speed > best):
            best = speed
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date')
    args = parser.parse_args()

    episodes = load_episodes(args.date)
    print(f'{len(episodes)} episodes\n')

    # --- 1. standing or moving -------------------------------------------
    judged = [(e, is_standing(e)) for e in episodes]
    standing = [e for e, s in judged if s is True]
    moving = [e for e, s in judged if s is False]
    unknown = [e for e, s in judged if s is None]
    print('STANDING OR MOVING')
    print(f'  {len(moving)} moving, {len(standing)} standing, '
          f'{len(unknown)} too few points to say')

    # The test: a standing episode should never take part in a journey
    # between two stations, because it did not go anywhere.
    import movement_tracker as mt
    by_day: dict[str, list] = {}
    for e in episodes:
        by_day.setdefault(e['t_enter'][:10], []).append(e)
    chained = set()
    for day, group in by_day.items():
        for m in mt.build_movements(group):
            if len({o['station'] for o in m['_chain']}) > 1:
                for o in m['_chain']:
                    chained.add(o['episode']['t_enter'])
    wrong = [e for e in standing if e['t_enter'] in chained]
    print(f'  of the {len(standing)} called standing, {len(wrong)} still '
          f'appear in a journey between stations')
    if moving:
        share = len(standing) / len(episodes)
        print(f'  {share:.0%} of episodes are a train that did not move')

    # --- 2. length and light engines --------------------------------------
    lengths = [(e, train_length_m(e)) for e in episodes]
    measured = [(e, m) for e, m in lengths if m]
    print(f'\nTRAIN LENGTH\n  measurable on {len(measured)} of {len(episodes)}')
    if measured:
        values = sorted(m for _, m in measured)
        print(f'  range {values[0]:.0f}-{values[-1]:.0f} m, '
              f'median {values[len(values) // 2]:.0f} m')
        light = [e for e, m in measured if m < LIGHT_ENGINE_M]
        print(f'  {len(light)} under {LIGHT_ENGINE_M:.0f} m, so a light engine '
              f'or a single unit')
        for e, m in sorted(measured, key=lambda p: p[1])[:4]:
            print(f'    {e["t_enter"][11:19]} {e["camera"]:<26} {m:5.0f} m')

    # --- 3. speed, against an independent estimate ------------------------
    print('\nSPEED')
    pairs = []
    for day, group in by_day.items():
        for m in mt.build_movements(group):
            if len(m['_chain']) < 2:
                continue
            summary = mt._summarise(m['_chain'])
            between = summary.get('avg_mph')
            if not between:
                continue
            for o in m['_chain']:
                within = observed_speed(o['episode'])
                if within:
                    pairs.append((o['episode'], within, between))
    print(f'  {len(pairs)} sightings have both a within-frame speed and a '
          f'station-to-station one')
    for episode, within, between in pairs[:6]:
        print(f'    {episode["t_enter"][11:19]} {episode["camera"]:<26} '
              f'{within:5.1f} mph in frame vs {between:5.1f} mph between stations')
    if pairs:
        gaps = [abs(a - b) for _, a, b in pairs]
        print(f'  median disagreement {sorted(gaps)[len(gaps) // 2]:.1f} mph')

    # --- 4. headcode ------------------------------------------------------
    print('\nHEADCODE')
    print('  not yet extracted — needs a vision call, prototyped separately')
    print('  candidate: D7017 carried 1M65 in large characters on 30/8')


if __name__ == '__main__':
    main()
