"""Upload detected episodes to Firestore for manual verification.

The detection pipeline writes with the admin SDK, so security rules can
keep clients from creating or altering detection data — they may only set
the verification fields. This mirrors the server-writes-only pattern used
for the football-team-picker error stats.

Against the emulator (no credentials needed):
    FIRESTORE_EMULATOR_HOST=localhost:8085 \\
    python3 upload_episodes.py --project demo-wsr

Against a real project:
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json \\
    python3 upload_episodes.py --project <project-id>

Episode media stays on disk by default: clips are training data, not
review material. --media uploads the stills and clips the episodes name
to Cloud Storage, where the deployed control room can read them under
storage.rules. It is idempotent, so running it after every pass costs one
listing and nothing else.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
CAPTURES = HERE / 'captures'
COLLECTION = 'episodes'
# A heartbeat, so the control room can tell "nothing is being detected" from
# "nothing has reached me". Without it a stale upload looked exactly like a
# stopped watcher, and the health panel accused capture of failing while the
# watcher was running perfectly and writing to disk.
STATUS = 'status'
MOVEMENTS = 'movements'
CAMERAS_COLLECTION = 'cameras'


def movement_document(movement: dict, record: dict, date_key: str) -> dict:
    """One journey: the same train recognised at several cameras.

    An episode on its own says a train passed one camera. The movement is
    what the operator actually wants to see — where it started, where it
    got to, how the delay ran on, and which sightings support that.
    """
    scheduled = record.get('scheduled') or {}
    return {
        'date_key': date_key,
        'first_seen': record['first_seen'],
        'last_seen': record['last_seen'],
        'from': record['from'],
        'to': record['to'],
        'direction': record['direction'],
        'sightings': record['sightings'],
        'miles': record['miles'],
        'avg_mph': record['avg_mph'],
        'identity': record.get('identity'),
        'observations': record['observations'],
        'kind': 'scheduled' if scheduled else 'unscheduled',
        'booked_departure': scheduled.get('booked_departure'),
        'serviceType': scheduled.get('serviceType'),
        'loco': scheduled.get('loco'),
        'delay_min': scheduled.get('delay_min'),
        'delay_start_min': scheduled.get('delay_start_min'),
        'delay_end_min': scheduled.get('delay_end_min'),
        'episode_ids': [episode_id(o['episode']) for o in movement['_chain']],
        'uploaded_at': datetime.now().isoformat(timespec='seconds'),
    }


def movement_id(record: dict, date_key: str) -> str:
    return (f"{date_key.replace('-', '')}_{record['first_seen'].replace(':', '')}"
            f"_{record['from']}_{record['to']}")


def load_readings() -> dict:
    """What the classifier read off each train, keyed by (time, camera).

    Two hundred and fifteen of these have been sitting in
    classifications.json since the first day and never reached the control
    room, so the one thing a person could actually check against a picture
    — is that a steam locomotive, is that the number — was the one thing
    the page did not show.
    """
    path = HERE / 'classifications.json'
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {(when, entry.get('camera')): entry for when, entry in raw.items()}


def reading_document(reading: dict | None) -> dict | None:
    """The classifier's reading, or nothing rather than a guess dressed up."""
    if not reading:
        return None
    traction = reading.get('traction')
    if traction in (None, '', 'unsure') and not reading.get('number'):
        return {'traction': 'unsure', 'train_class': None, 'number': None,
                'livery': reading.get('livery') or None,
                'confidence': reading.get('confidence'),
                'notes': (reading.get('notes') or '')[:240] or None}
    return {
        'traction': traction or None,
        'train_class': reading.get('train_class') or None,
        'number': reading.get('number') or None,
        'livery': reading.get('livery') or None,
        'confidence': reading.get('confidence'),
        'notes': (reading.get('notes') or '')[:240] or None,
    }


def track_summary(track: dict) -> dict:
    """One train the tracker held, flattened for Firestore.

    Firestore refuses an array inside an array, and a track carries both a
    path of coordinate triples and a drift pair. Neither is wanted here
    anyway: what a person weighing a detection needs is how long the train
    was held, whether it moved and how far, not where every centroid sat.
    """
    drift = track.get('drift_px') or [0, 0]
    return {
        'id': track.get('id'),
        't_enter': track.get('t_enter'),
        't_exit': track.get('t_exit'),
        'observations': track.get('observations'),
        'peak_conf': track.get('peak_conf'),
        'moved': track.get('moved'),
        'drift_x': drift[0],
        'drift_y': drift[1] if len(drift) > 1 else 0,
        'zones': ', '.join(track.get('zones') or []),
    }


def episode_document(episode: dict, movement: dict | None,
                     corroboration: dict | None = None,
                     reading: dict | None = None) -> dict:
    """One Firestore document: what was detected, and what we think it was."""
    scheduled = (movement or {}).get('scheduled')
    return {
        # --- detection facts (pipeline-owned, clients cannot change) ---
        'camera': episode['camera'],
        't_enter': episode['t_enter'],
        't_exit': episode.get('t_exit'),
        'date_key': episode['t_enter'][:10],
        'direction': episode.get('direction'),
        'zones': episode.get('zones', []),
        'peak_conf': episode.get('peak_conf'),
        'observations': episode.get('n_observations'),
        'drift_px': episode.get('drift_px'),
        # What the tracker made of it, which is the strongest evidence a
        # person can weigh: how many separate trains it held, how many of
        # them moved, and whether the path jumped — a jump is why a
        # direction comes back unclear, and saying so is more use than
        # hiding the field.
        'tracks': [track_summary(t) for t in (episode.get('tracks') or [])],
        'trains_moving': episode.get('trains_moving'),
        # What was read off the train itself — traction, class, running
        # number. Derived from a still by a classifier, so it is offered as
        # something to check rather than as fact.
        'reading': reading_document(reading),
        'path_jumps': episode.get('path_jumps'),
        'most_in_frame': episode.get('most_in_frame'),
        'keyframe': (episode.get('keyframes') or [None])[0],
        'hires': episode.get('hires'),
        # Boxes travel as data beside the clean still, so the overlay can be
        # turned off to read a running number underneath — and so a
        # classifier is given the photograph, not the annotation. Keyed by
        # image, and matched to whichever still the UI shows: the hi-res
        # one where there is one, since that is the clean copy.
        'boxes': next(
            ({**boxes, 'image': name}
             for name, boxes in (episode.get('boxes') or {}).items()
             if name in (episode.get('hires'),
                         (episode.get('keyframes') or [None])[0])),
            None),
        'clip': episode.get('clip'),
        # The stream-rate clip, where there is one: 25fps of the passage
        # rather than a frame every five seconds, which is what makes a
        # detection judgeable by eye.
        'dense_clip': episode.get('dense_clip'),
        'dense_frames': episode.get('dense_frames_kept'),

        # --- the system's claim, for a human to confirm or correct ---
        'claim': {
            'kind': 'scheduled' if scheduled else 'unscheduled',
            'booked_departure': scheduled.get('booked_departure') if scheduled else None,
            'serviceType': scheduled.get('serviceType') if scheduled else None,
            'loco': scheduled.get('loco') if scheduled else None,
            'delay_min': scheduled.get('delay_min') if scheduled else None,
            'corroborating_sightings': (movement or {}).get('sightings'),
        },

        # Whether the second camera watching the same rails saw it too.
        # Independent of any human, and the signal that shows a camera
        # detecting things its partner cannot see.
        'corroboration': corroboration,

        'uploaded_at': datetime.now().isoformat(timespec='seconds'),
    }


# Verification state lives in its own fields so a re-upload can refresh the
# detection claim without discarding a human's answer.
INITIAL_VERIFICATION = {'status': 'unverified', 'verification': None}


def episode_id(episode: dict) -> str:
    """Stable id so re-running the uploader updates rather than duplicates."""
    return f"{episode['t_enter'].replace(':', '').replace('-', '')}_{episode['camera']}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--date', default=None, help='only upload this date_key')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--media', action='store_true',
                        help='also upload the stills and clips to Cloud Storage')
    parser.add_argument('--bucket', default=None,
                        help='defaults to <project>-captures')
    args = parser.parse_args()

    from episode_analysis import load_episodes
    from movement_tracker import annotate, build_movements

    episodes = load_episodes()
    if args.date:
        episodes = [e for e in episodes if e['t_enter'].startswith(args.date)]
    if not episodes:
        print('no episodes to upload')
        return

    # map each episode to the movement that explains it, so the uploaded
    # claim carries the corroborated view rather than a lone sighting
    date_key = episodes[0]['t_enter'][:10]
    movements = build_movements(episodes)
    annotated = annotate(movements, date_key)
    claim_for: dict[str, dict] = {}
    for movement, record in zip(movements, annotated):
        for obs in movement['_chain']:
            claim_for[obs['episode']['t_enter']] = {**record,
                                                    'sightings': movement['sightings']}

    from corroboration import corroborate
    verdicts = corroborate(episodes)
    readings = load_readings()
    documents = [(episode_id(e),
                  episode_document(e, claim_for.get(e['t_enter']),
                                   verdicts.get(episode_id(e)),
                                   readings.get((e['t_enter'], e['camera']))))
                 for e in episodes]
    read = sum(1 for _, d in documents if d.get('reading'))
    print(f'{read} episodes carry a reading off the train')
    scheduled = sum(1 for _, d in documents if d['claim']['kind'] == 'scheduled')
    print(f'{len(documents)} episodes '
          f'({scheduled} scheduled, {len(documents) - scheduled} unscheduled)')

    movement_docs = [(movement_id(record, date_key),
                      movement_document(movement, record, date_key))
                     for movement, record in zip(movements, annotated)]
    matched = sum(1 for _, d in movement_docs if d['kind'] == 'scheduled')
    print(f'{len(movement_docs)} movements '
          f'({matched} matched to a service, {len(movement_docs) - matched} not)')

    from camera_registry import registry
    camera_docs = [(entry['id'], entry) for entry in registry()]
    print(f'{len(camera_docs)} cameras')

    if args.media:
        import media_upload
        names = media_upload.referenced(documents)
        if args.dry_run:
            print(f'{len(names)} files named by these episodes')
        else:
            from google.cloud import storage
            bucket_name = args.bucket or f'{args.project}-captures'
            bucket = storage.Client(project=args.project).bucket(bucket_name)
            summary = media_upload.upload(bucket, names)
            print(f'{bucket_name}: {media_upload.describe(summary)}')
            for name in summary['missing_locally'][:5]:
                print(f'  named but not on disk: {name}')

    if args.dry_run:
        for doc_id, doc in documents[:3]:
            print(f'  {doc_id}: {doc["claim"]}')
        for doc_id, doc in movement_docs[:3]:
            print(f"  {doc_id}: {doc['from']}->{doc['to']} "
                  f"{doc['sightings']} sightings, {doc['kind']}")
        print('dry run — nothing written')
        return

    import firebase_admin
    from firebase_admin import firestore

    if os.environ.get('FIRESTORE_EMULATOR_HOST'):
        print(f"using emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}")
        firebase_admin.initialize_app(options={'projectId': args.project})
    else:
        firebase_admin.initialize_app(options={'projectId': args.project})

    client = firestore.client()
    collection = client.collection(COLLECTION)
    existing = {snapshot.id for snapshot in collection.select([]).stream()}

    batch = client.batch()
    written = new = 0
    for doc_id, doc in documents:
        payload = dict(doc)
        if doc_id not in existing:
            payload.update(INITIAL_VERIFICATION)   # only ever set on create
            new += 1
        batch.set(collection.document(doc_id), payload, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = client.batch()
    batch.commit()
    print(f'wrote {written} documents to {COLLECTION} '
          f'({new} new, {written - new} refreshed without touching verification)')

    latest = max((e['t_enter'] for e in episodes), default=None)
    client.collection(STATUS).document('pipeline').set({
        'uploaded_at': datetime.now().isoformat(timespec='seconds'),
        'episodes': written,
        'latest_episode': latest,
        'date_key': args.date,
    })
    print(f'heartbeat written: latest episode {latest}')

    # Movements and cameras are derived, so they are replaced outright
    # rather than merged — nothing a verifier owns lives on them.
    for name, docs in ((MOVEMENTS, movement_docs),
                       (CAMERAS_COLLECTION, camera_docs)):
        target = client.collection(name)
        batch = client.batch()
        for index, (doc_id, doc) in enumerate(docs, 1):
            batch.set(target.document(doc_id), doc)
            if index % 400 == 0:
                batch.commit()
                batch = client.batch()
        batch.commit()
        print(f'wrote {len(docs)} documents to {name}')


if __name__ == '__main__':
    main()
