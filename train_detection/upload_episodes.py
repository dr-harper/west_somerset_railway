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
import hashlib
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

# What was last written, so a run that changes nothing costs nothing.
#
# Every run rewrote the day in full — 549 documents whether or not a single
# one had changed. Run every quarter of an hour, as it now is, that is about
# 52,000 writes a day against a free tier of 20,000: the automation that was
# meant to keep the control room current would have started billing for
# writing the same bytes back over themselves.
#
# Local rather than remote on purpose. Asking Firestore what it already has
# costs a read per document, which is the same problem wearing a different
# hat.
MANIFEST = HERE / '.uploaded.json'


# Stamped fresh on every run, so it makes an untouched episode look changed.
# Hashing it defeated the whole point: the first attempt at skipping
# unchanged documents still rewrote all 549, because every one of them
# carried a new uploaded_at.
VOLATILE = frozenset({'uploaded_at'})


def fingerprint(payload: dict) -> str:
    """A stable hash of what would be written, ignoring the clock.

    Leaving uploaded_at out has a second, better effect: it stops meaning
    "when the pipeline last ran" — which the heartbeat already records — and
    starts meaning "when this episode last actually changed", which is the
    more useful of the two and was not recorded anywhere.
    """
    stable = {k: v for k, v in payload.items() if k not in VOLATILE}
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text())
    except (OSError, json.JSONDecodeError):
        # No manifest, or a corrupt one, means write everything once. That
        # is the safe direction to fail in.
        return {}


def save_manifest(manifest: dict) -> None:
    # Written via a temporary file so an interrupted run cannot leave a
    # half-written manifest that would be read as "already uploaded".
    scratch = MANIFEST.with_suffix('.tmp')
    scratch.write_text(json.dumps(manifest, sort_keys=True))
    scratch.replace(MANIFEST)


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


def deduplicate(episodes: list) -> list:
    """One record per episode, keeping the most complete.

    episodes.jsonl is append-only, so an episode that was still open when it
    was first written and later grew appears twice: same start, same camera,
    a longer t_exit the second time. Both map to the same document id, so
    each upload wrote one then the other and the control room showed
    whichever landed last — 8 episodes on 31/8 alternated between a 80
    second passage and a 5 minute one on every run.

    The later ending is the better record: it saw the train for longer and,
    in every colliding pair here, with more confidence.
    """
    best: dict = {}
    for episode in episodes:
        key = episode_id(episode)
        held = best.get(key)
        if held is None or (episode.get('t_exit') or '') > (held.get('t_exit') or ''):
            best[key] = episode
    return list(best.values())


def episode_id(episode: dict) -> str:
    """Stable id so re-running the uploader updates rather than duplicates."""
    return f"{episode['t_enter'].replace(':', '').replace('-', '')}_{episode['camera']}"


def firestore_client(project: str):
    """A Firestore client, however this machine happens to be authenticated.

    On the VM the service account is the ambient identity and nothing needs
    saying. On a laptop that shares a login with other work, the default
    credentials belong to whichever account was last active — which here is
    a different Google account entirely, so uploads failed with a permission
    error naming the wrong user and no obvious way to point them elsewhere
    short of switching the whole machine over.

    WSR_ACCESS_TOKEN takes an OAuth token for the right account instead, so
    the upload can be aimed at this project without disturbing anything the
    other account is in the middle of:

        WSR_ACCESS_TOKEN=$(gcloud auth print-access-token --account=<you>)
    """
    if os.environ.get('FIRESTORE_EMULATOR_HOST'):
        print(f"using emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}")
        import firebase_admin
        from firebase_admin import firestore
        firebase_admin.initialize_app(options={'projectId': project})
        return firestore.client()

    token = os.environ.get('WSR_ACCESS_TOKEN')
    if token:
        from google.cloud import firestore as gcf
        from google.oauth2.credentials import Credentials
        print(f'using an explicit access token for {project}')
        return gcf.Client(project=project, credentials=Credentials(token=token))

    import firebase_admin
    from firebase_admin import firestore
    firebase_admin.initialize_app(options={'projectId': project})
    return firestore.client()


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
    before = len(episodes)
    episodes = sorted(deduplicate(episodes), key=lambda e: e['t_enter'])
    if before != len(episodes):
        print(f'{before - len(episodes)} duplicate records collapsed '
              f'into the episode they belong to')
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
            # Same authentication problem as Firestore, and the same answer:
            # the ambient credentials on this laptop belong to another
            # account entirely.
            token = os.environ.get('WSR_ACCESS_TOKEN')
            if token:
                from google.oauth2.credentials import Credentials
                client = storage.Client(project=args.project,
                                        credentials=Credentials(token=token))
            else:
                client = storage.Client(project=args.project)
            bucket = client.bucket(bucket_name)
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

    client = firestore_client(args.project)
    collection = client.collection(COLLECTION)
    existing = {snapshot.id for snapshot in collection.select([]).stream()}

    manifest = load_manifest()
    batch = client.batch()
    written = new = unchanged = 0
    for doc_id, doc in documents:
        payload = dict(doc)
        if doc_id not in existing:
            payload.update(INITIAL_VERIFICATION)   # only ever set on create
            new += 1
        mark = fingerprint(payload)
        # An episode that has not changed since it was last written is
        # skipped. A verifier's own edits are unaffected: this compares what
        # the pipeline would write, and the pipeline never writes the
        # verification fields after create.
        if manifest.get(f'{COLLECTION}/{doc_id}') == mark and doc_id in existing:
            unchanged += 1
            continue
        batch.set(collection.document(doc_id), payload, merge=True)
        manifest[f'{COLLECTION}/{doc_id}'] = mark
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = client.batch()
    batch.commit()
    print(f'wrote {written} documents to {COLLECTION} '
          f'({new} new, {written - new} changed, {unchanged} unchanged and skipped)')

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
        sent = skipped = 0
        for doc_id, doc in docs:
            mark = fingerprint(doc)
            if manifest.get(f'{name}/{doc_id}') == mark:
                skipped += 1
                continue
            batch.set(target.document(doc_id), doc)
            manifest[f'{name}/{doc_id}'] = mark
            sent += 1
            if sent % 400 == 0:
                batch.commit()
                batch = client.batch()
        batch.commit()
        print(f'wrote {sent} documents to {name} ({skipped} unchanged)')

    # Only after every commit has gone through, so a failure part way leaves
    # the manifest behind reality rather than ahead of it. Behind means a
    # harmless rewrite next run; ahead means a document silently never
    # written at all.
    save_manifest(manifest)


if __name__ == '__main__':
    main()
