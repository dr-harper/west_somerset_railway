"""Two cameras watching the same railway, checking each other's work.

Four places have a second camera pointed at the same stretch of line. When
both see a train at once that is independent confirmation, obtained
without anyone labelling anything. When one sees a train and the other,
looking at the same rails at the same moment, sees nothing, that is a
detection worth doubting.

The signal is strong. On 30/8 Williton reported 20 episodes and 18 were
confirmed by its partner; Williton 2 reported 91 and only 38 were. The
difference is a roof in the foreground that YOLO reads as a train — a
fault that took a week to find by hand and that this would have shown on
the first day.

Two traps, both of which the plain "same station" grouping falls into:

  A silent partner is not disagreement. Crowcombe 2 has no traced track
  so it detects nothing at all, which would score Crowcombe 1 at zero.

  Sharing a station is not sharing a view. Minehead station and Seaward
  Crossing are both filed under MIN but look at different places, so a
  train at the platform is genuinely invisible to the other.

So the pairs here are the ones that actually overlap, listed rather than
derived.

    python3 corroboration.py [--date 2026-08-30]
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent

# Cameras whose views cover the same rails. Not every pair at a station:
# see the module docstring on Minehead.
VIEW_PAIRS = [
    ('crowcombe_heathfield', 'crowcombe_heathfield_2'),
    ('williton', 'williton_2'),
    ('watchet_1', 'watchet_visitor_centre'),
    ('blue_anchor', 'blue_anchor_2'),
]

PARTNER = {}
for _a, _b in VIEW_PAIRS:
    PARTNER[_a] = _b
    PARTNER[_b] = _a


def span(episode: dict) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(episode['t_enter'])
    end = (datetime.fromisoformat(episode['t_exit'])
           if episode.get('t_exit') else start)
    return start, end


def episode_id(episode: dict) -> str:
    stamp = episode['t_enter'].replace(':', '').replace('-', '')
    return f"{stamp}_{episode['camera']}"


def roads(episode: dict) -> set[str]:
    """Which roads the detection was placed on, e.g. running line, loop."""
    return {z for z in (episode.get('zones') or []) if z}


def corroborate(episodes: list[dict]) -> dict[str, dict]:
    """For each episode, whether its partner camera saw the same train.

    Overlap in time rather than a window around the start: two cameras
    catch a train at different moments of its passage, and asking whether
    both had it in view at once needs no threshold to be argued over.

    Time alone is not enough, though. Williton is a crossing place near
    the middle of the line, so two trains are often there at once — one
    standing in the loop while another runs through. Two cameras seeing a
    train at the same moment may be seeing different trains, which would
    be counted as confirmation when it is nothing of the kind. So they
    must also agree on the road: loop with loop, running line with running
    line. A pair that overlaps in time but not in road is two trains, and
    is recorded as such rather than being quietly discarded.
    """
    by_camera: dict[str, list] = {}
    for episode in episodes:
        by_camera.setdefault(episode['camera'], []).append(episode)

    # The road test only means something where both cameras name their
    # roads the same way, and they frequently do not: a camera with
    # hand-drawn zones reports names like 'platform roads' and 'level
    # crossing', while one without reports the traced road names. Blue
    # Anchor's pair share no vocabulary at all, so comparing roads there
    # rejected every pairing and scored a healthy camera at zero.
    #
    # Judged on which source each camera draws from rather than on the
    # names seen so far, which depends on how much of a day has run.
    from detection_zones import ZONES
    def comparable_pair(a: str, b: str) -> bool:
        return (a in ZONES) == (b in ZONES)

    verdicts = {}
    for episode in episodes:
        camera = episode['camera']
        partner = PARTNER.get(camera)
        if not partner:
            verdicts[episode_id(episode)] = {'checkable': False,
                                             'reason': 'no second view'}
            continue
        theirs = by_camera.get(partner, [])
        if not theirs:
            # A camera that reports nothing all day cannot disagree.
            verdicts[episode_id(episode)] = {
                'checkable': False, 'reason': f'{partner} saw nothing today'}
            continue
        start, end = span(episode)
        mine = roads(episode)
        comparable = comparable_pair(camera, partner)
        # Several partner episodes can overlap when two trains are about,
        # so take the best rather than the first: same road before any
        # road, then the one closest in time. Matching the first overlap
        # would pair a train with whichever of the two happened to be
        # earlier in the file.
        candidates = []
        crossed = False
        for other in theirs:
            their_start, their_end = span(other)
            if not (their_start <= end and start <= their_end):
                continue
            same_road = bool(mine and roads(other) and (mine & roads(other)))
            if comparable and mine and roads(other) and not same_road:
                crossed = True      # both busy, but on different roads
                continue
            gap = abs((their_start - start).total_seconds())
            candidates.append((not same_road, gap, other))
        candidates.sort(key=lambda c: (c[0], c[1]))
        match = candidates[0][2] if candidates else None
        verdicts[episode_id(episode)] = {
            'checkable': True,
            'corroborated': match is not None,
            'partner': partner,
            'partner_episode': episode_id(match) if match else None,
            'other_road': crossed and match is None,
        }
    return verdicts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default='2026-08-30')
    args = parser.parse_args()

    episodes = [json.loads(line) for line
                in (HERE / 'episodes.jsonl').read_text().splitlines() if line.strip()]
    episodes = [e for e in episodes if e['t_enter'].startswith(args.date)]
    verdicts = corroborate(episodes)

    print(f"{'camera':<28} {'episodes':>9} {'confirmed':>10} {'alone':>7}  note")
    for camera in sorted({e['camera'] for e in episodes}):
        mine = [e for e in episodes if e['camera'] == camera]
        results = [verdicts[episode_id(e)] for e in mine]
        checkable = [r for r in results if r['checkable']]
        if not checkable:
            reason = results[0].get('reason', '') if results else ''
            print(f'{camera:<28} {len(mine):>9} {"—":>10} {"—":>7}  {reason}')
            continue
        yes = sum(1 for r in checkable if r['corroborated'])
        crossing = sum(1 for r in checkable if r.get('other_road'))
        alone = len(checkable) - yes
        share = yes / len(checkable)
        note = ''
        if share < 0.5:
            note = 'more often alone than confirmed — worth a look'
        if crossing:
            note = (note + '; ' if note else '') + \
                f'{crossing} where the partner had a train on the other road'
        print(f'{camera:<28} {len(mine):>9} {yes:>10} {alone:>7}  {note}')

    total = [v for v in verdicts.values() if v['checkable']]
    if total:
        yes = sum(1 for v in total if v['corroborated'])
        print(f'\n{yes} of {len(total)} checkable detections were seen by both '
              f'cameras ({yes / len(total):.0%})')
        print(f'{len(verdicts) - len(total)} could not be checked: no second '
              f'view, or the second camera saw nothing all day')


if __name__ == '__main__':
    main()
